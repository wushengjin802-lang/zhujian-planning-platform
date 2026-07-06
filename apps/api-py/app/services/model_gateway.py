from __future__ import annotations

import json
import urllib.error
import urllib.request

from app.core.config import settings


def gateway_configured() -> bool:
    return bool(settings.model_gateway_url)


def gateway_status() -> dict:
    if not settings.model_gateway_url:
        return {
            "configured": False,
            "available": False,
            "mode": settings.ai_mode,
            "message": "智能生成服务未配置，当前使用本地规则生成",
        }
    try:
        request = urllib.request.Request(f"{settings.model_gateway_url.rstrip('/')}/health")
        if settings.model_gateway_api_key:
            request.add_header("Authorization", f"Bearer {settings.model_gateway_api_key}")
        with urllib.request.urlopen(request, timeout=settings.model_gateway_timeout) as response:
            return {
                "configured": True,
                "available": 200 <= response.status < 300,
                "mode": "gateway",
                "message": response.read(300).decode("utf-8", errors="ignore"),
            }
    except Exception as exc:
        return {"configured": True, "available": False, "mode": "local_rules", "message": str(exc)}


def generate_text(prompt: str, context: list[dict]) -> dict:
    if not settings.model_gateway_url:
        return {"mode": "local_rules", "text": fallback_text(prompt, context), "raw": None}

    payload = json.dumps({"prompt": prompt, "context": context}, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        f"{settings.model_gateway_url.rstrip('/')}/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    if settings.model_gateway_api_key:
        request.add_header("Authorization", f"Bearer {settings.model_gateway_api_key}")
    try:
        with urllib.request.urlopen(request, timeout=settings.model_gateway_timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
            return {"mode": "gateway", "text": data.get("text") or data.get("content") or "", "raw": data}
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return {"mode": "local_rules", "text": fallback_text(prompt, context), "raw": {"error": str(exc)}}


def fallback_text(prompt: str, context: list[dict]) -> str:
    facts = [item for item in context if item.get("type") == "fact"]
    chunks = [item for item in context if item.get("type") == "chunk"]
    lines = [prompt, "", "以下内容由本地规则生成，需专业人员复核："]
    lines.extend(f"- {item['name']}：{item['value']}{item.get('unit') or ''}（来源：{item['source']}）" for item in facts)
    if chunks:
        lines.append("")
        lines.append("资料依据摘录：")
        lines.extend(f"- {item['locator']}：{item['content'][:120]}" for item in chunks[:4])
    return "\n".join(lines)
