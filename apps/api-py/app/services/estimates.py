"""Investment estimation — computes breakdown and sensitivity from project facts."""

from __future__ import annotations

import time
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.db.models import AuditLog, FactItem, InvestmentEstimate

# ── default breakdown ratios (configurable per project type) ──

DEFAULT_RATIOS: dict[str, float] = {
    "工程费用": 0.65,
    "工程建设其他费用": 0.18,
    "预备费": 0.08,
    "建设期利息": 0.05,
    "铺底流动资金": 0.04,
}

# ── sensitivity scenarios ──

SENSITIVITY_SCENARIOS: list[float] = [-0.20, -0.10, 0.0, 0.10, 0.20]


def _parse_num(value: str) -> Decimal | None:
    """Extract a numeric value from a fact string, removing commas."""
    import re

    cleaned = value.replace(",", "").replace("，", "")
    m = re.search(r"-?\d+(?:\.\d+)?", cleaned)
    return Decimal(m.group(0)) if m else None


def _qty(dec: Decimal, precision: int = 2) -> str:
    """Round to 2 decimal places and drop trailing zeros."""
    return str(dec.quantize(Decimal("0.1") ** precision, rounding=ROUND_HALF_UP).normalize())


def _collect_inputs(db: Session, project_id: str) -> dict:
    """Walk project facts and extract investment-related numbers."""
    facts = db.scalars(
        select(FactItem).where(FactItem.project_id == project_id).order_by(FactItem.id)
    ).all()

    inputs: dict[str, Decimal | str] = {}
    for f in facts:
        if f.status == "有冲突":
            continue  # skip conflicting facts
        num = _parse_num(f.value)
        if num is not None:
            inputs[f.name] = num
        else:
            inputs[f.name] = f.value

    return inputs


def calculate_estimate(db: Session, project_id: str) -> InvestmentEstimate:
    """Run a full investment estimation for the given project."""

    inputs = _collect_inputs(db, project_id)

    total_raw = inputs.get("项目总投资")
    # also look for "建设总投资" / "总投资"
    if not total_raw:
        for k in ("建设总投资", "总投资", "估算总投资"):
            v = inputs.get(k)
            if isinstance(v, Decimal):
                total_raw = v
                break

    total = Decimal(total_raw) if isinstance(total_raw, Decimal) else Decimal("0")

    # ── compute per-category breakdown ──
    breakdown: list[dict] = []
    for category, ratio in DEFAULT_RATIOS.items():
        amount = total * Decimal(str(ratio))
        breakdown.append(
            {
                "category": category,
                "ratio": ratio,
                "amount": _qty(amount),
                "amount_raw": float(amount),
            }
        )

    # ── per-unit metrics ──
    unit_metrics: dict[str, dict] = {}
    for key in inputs:
        if isinstance(inputs[key], Decimal) and key != "项目总投资" and "面积" in key:
            area = Decimal(inputs[key])
            if area > 0:
                unit_price = total / area
                unit_metrics[key] = {
                    "area": _qty(area),
                    "unitInv": _qty(unit_price),
                    "unitInvRaw": float(unit_price),
                }

    # ── funding structure ──
    funding: dict = {}
    special_bond_pct = inputs.get("专项债资金占比")
    if isinstance(special_bond_pct, Decimal) and total > 0:
        sb_ratio = special_bond_pct / Decimal("100")
        sb_amount = total * sb_ratio
        own_amount = total - sb_amount
        funding = {
            "专项债资金": {"ratio": float(special_bond_pct) / 100, "amount": _qty(sb_amount)},
            "自有资金": {
                "ratio": float(Decimal("1") - sb_ratio),
                "amount": _qty(own_amount),
            },
        }

    # ── sensitivity analysis ──
    sensitivity: list[dict] = []
    if total > 0:
        base_construction = total * Decimal(str(DEFAULT_RATIOS["工程费用"]))
        base_contingency = total * Decimal(str(DEFAULT_RATIOS["预备费"]))

        for delta in SENSITIVITY_SCENARIOS:
            # vary construction cost
            varied_construction = base_construction * (Decimal("1") + Decimal(str(delta)))
            varied_total = (
                varied_construction
                + total * Decimal(str(DEFAULT_RATIOS["工程建设其他费用"]))
                + base_contingency
                + total * Decimal(str(DEFAULT_RATIOS["建设期利息"]))
                + total * Decimal(str(DEFAULT_RATIOS["铺底流动资金"]))
            )
            change_pct = (varied_total - total) / total if total > 0 else Decimal("0")
            sensitivity.append(
                {
                    "scenario": f"工程费用变动{int(delta * 100):+d}%",
                    "delta": delta,
                    "totalVariant": _qty(varied_total),
                    "changePct": _qty(change_pct * Decimal("100")),
                    "changePctRaw": float(change_pct),
                }
            )

    # ── persist ──
    estimate = InvestmentEstimate(
        id=f"EST-{int(time.time() * 1000)}",
        project_id=project_id,
        status="calculated",
        input_snapshot={k: str(v) for k, v in inputs.items()},
        output={
            "totalInvestment": _qty(total),
            "totalInvestmentRaw": float(total),
            "breakdown": breakdown,
            "unitMetrics": unit_metrics,
            "funding": funding,
        },
        sensitivity=sensitivity,
    )
    db.add(estimate)
    db.add(
        AuditLog(
            actor="system",
            action="calculate_estimate",
            entity_type="investment_estimate",
            entity_id=estimate.id,
            detail={"projectId": project_id, "totalInvestment": _qty(total)},
        )
    )
    db.commit()
    return estimate


def confirm_estimate(db: Session, estimate_id: str, user_name: str) -> InvestmentEstimate:
    estimate = db.get(InvestmentEstimate, estimate_id)
    if not estimate:
        raise ValueError("Investment estimate not found")
    estimate.status = "confirmed"
    estimate.confirmed_by = user_name
    estimate.confirmed_at = db.scalar(select(func.now()))
    db.add(
        AuditLog(
            actor=user_name,
            action="confirm_estimate",
            entity_type="investment_estimate",
            entity_id=estimate_id,
            detail={"status": "confirmed"},
        )
    )
    db.commit()
    return estimate


def get_estimate(db: Session, project_id: str) -> InvestmentEstimate | None:
    return db.scalars(
        select(InvestmentEstimate)
        .where(InvestmentEstimate.project_id == project_id)
        .order_by(InvestmentEstimate.created_at.desc())
    ).first()


def map_estimate(est: InvestmentEstimate) -> dict:
    return {
        "id": est.id,
        "projectId": est.project_id,
        "status": est.status,
        "inputSnapshot": est.input_snapshot,
        "output": est.output,
        "sensitivity": est.sensitivity,
        "confirmedBy": est.confirmed_by,
        "confirmedAt": est.confirmed_at.isoformat() if est.confirmed_at else None,
        "createdAt": est.created_at.isoformat(),
    }
