from __future__ import annotations

import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api-py"))

from app.main import app


def assert_ok(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    client = TestClient(app)

    health = client.get("/health")
    assert_ok(health.status_code == 200 and health.json()["ok"], "health failed")

    login = client.post("/api/auth/login", json={"email": "owner@zhujian.local", "password": "demo123"})
    assert_ok(login.status_code == 200, f"login failed: {login.text}")
    token = login.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    bootstrap = client.get("/api/bootstrap")
    assert_ok(bootstrap.status_code == 200, "bootstrap failed")
    payload = bootstrap.json()
    project = payload["projects"][0]

    source_path = ROOT / "samples" / "phase1_demo_source.md"
    with source_path.open("rb") as file:
        upload = client.post(
            f"/api/projects/{project['id']}/documents/upload",
            files={"file": (source_path.name, file, "text/markdown")},
            headers=headers,
        )
    assert_ok(upload.status_code == 201, f"upload failed: {upload.text}")
    document = upload.json()

    parse = client.post(f"/api/documents/{document['id']}/parse", headers=headers)
    assert_ok(parse.status_code == 202, f"parse failed: {parse.text}")

    chapter_id = payload["chapters"][0]["id"]
    chapter = client.post(f"/api/chapters/{chapter_id}/generate", headers=headers)
    assert_ok(chapter.status_code == 202, f"chapter generation failed: {chapter.text}")

    quality = client.post("/api/quality/checks", json={"projectId": project["id"]}, headers=headers)
    assert_ok(quality.status_code == 202, f"quality check failed: {quality.text}")

    refreshed = client.get("/api/bootstrap").json()
    excel = next(item for item in refreshed["artifacts"] if item["format"] == "Excel" and item["projectId"] == project["id"])
    export = client.post(f"/api/artifacts/{excel['id']}/export", headers=headers)
    assert_ok(export.status_code == 202, f"artifact export failed: {export.text}")

    final_payload = client.get("/api/bootstrap").json()
    project_docs = [item for item in final_payload["documents"] if item["projectId"] == project["id"]]
    citations = [item for item in final_payload["citations"] if item["chapterId"] == chapter_id]
    assert_ok(any(item["chunkCount"] > 0 for item in project_docs), "no parsed chunks found")
    assert_ok(citations, "no citations found")

    print(
        json.dumps(
            {
                "status": "passed",
                "project": project["id"],
                "uploadedDocument": document["id"],
                "parseExecution": parse.json().get("execution"),
                "qualityExecution": quality.json().get("execution"),
                "exportExecution": export.json().get("execution"),
                "citations": len(citations),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
