from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from app.core.config import settings


def libreoffice_binary() -> str | None:
    candidates = [settings.libreoffice_path, "soffice", "libreoffice"]
    for candidate in candidates:
        if not candidate:
            continue
        resolved = shutil.which(candidate) or (candidate if Path(candidate).exists() else None)
        if resolved:
            return resolved
    return None


def libreoffice_status() -> dict:
    binary = libreoffice_binary()
    if not binary:
        return {"available": False, "binary": None, "message": "成果转换服务未配置"}
    try:
        result = subprocess.run([binary, "--version"], capture_output=True, text=True, timeout=5, check=False)
        return {
            "available": result.returncode == 0,
            "binary": binary,
            "message": (result.stdout or result.stderr).strip()[:200],
        }
    except Exception as exc:
        return {"available": False, "binary": binary, "message": str(exc)}


def convert_bytes_to_pdf(data: bytes, source_name: str) -> bytes | None:
    binary = libreoffice_binary()
    if not binary:
        return None

    suffix = Path(source_name).suffix or ".docx"
    with tempfile.TemporaryDirectory() as tmpdir:
        workdir = Path(tmpdir)
        source = workdir / f"source{suffix}"
        source.write_bytes(data)
        result = subprocess.run(
            [binary, "--headless", "--convert-to", "pdf", "--outdir", str(workdir), str(source)],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        if result.returncode != 0:
            return None
        pdf = source.with_suffix(".pdf")
        return pdf.read_bytes() if pdf.exists() else None
