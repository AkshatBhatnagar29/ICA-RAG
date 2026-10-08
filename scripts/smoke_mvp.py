"""Run a concise authenticated MVP smoke test without printing sensitive payloads.

Required environment: ICIA_SMOKE_EMAIL and ICIA_SMOKE_PASSWORD.
The default upload is data/raw/contracts/icat-version1/PDFs/PDFs/Standard-agreement.pdf.
Override it with ICIA_SMOKE_FILE when needed.
Optional: ICIA_SMOKE_SECOND_FILE for comparison coverage.
"""
from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SMOKE_FILE = ROOT / "data/raw/contracts/icat-version1/PDFs/PDFs/Standard-agreement.pdf"


def main() -> int:
    email = os.environ.get("ICIA_SMOKE_EMAIL")
    password = os.environ.get("ICIA_SMOKE_PASSWORD")
    source = Path(os.environ["ICIA_SMOKE_FILE"]) if os.environ.get("ICIA_SMOKE_FILE") else DEFAULT_SMOKE_FILE
    second = Path(os.environ["ICIA_SMOKE_SECOND_FILE"]) if os.environ.get("ICIA_SMOKE_SECOND_FILE") else None
    if not email or not password or not source.is_file():
        print(f"FAIL configuration: set ICIA_SMOKE_EMAIL and ICIA_SMOKE_PASSWORD; missing file: {source}")
        return 2
    base = os.environ.get("ICIA_SMOKE_BASE_URL", "http://localhost:8000/api/v1")
    with httpx.Client(timeout=180.0) as client:
        checks: list[str] = []
        for name in ("health", "ready"):
            response = client.get(f"{base}/{name}")
            response.raise_for_status()
            checks.append(name)
        token_response = client.post(f"{base}/auth/token", data={
            "username": email, "password": password, "grant_type": "password"})
        token_response.raise_for_status()
        token = token_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        upload = client.post(f"{base}/documents", headers=headers, files={
            "file": (source.name, source.read_bytes(), "application/pdf")},
            data={"title": f"smoke-{source.stem}-{uuid.uuid4().hex[:8]}", "document_type": "contract"})
        upload.raise_for_status()
        first = upload.json()
        version = first["version_id"]
        analysis = client.post(f"{base}/contracts/{version}/analyze", headers=headers, json={})
        analysis.raise_for_status()
        search = client.post(f"{base}/search", headers=headers, json={
            "query": "case title", "scope": {"document_version_id": version},
            "top_k": 5, "mode": "hybrid", "rerank": True})
        search.raise_for_status()
        chat = client.post(f"{base}/chat", headers=headers, json={
            "query": "What is the court name?", "document_version_id": version,
            "top_k": 5, "mode": "hybrid", "rerank": True})
        chat.raise_for_status()
        chat_result = chat.json()
        if not chat_result.get("answer") or not chat_result.get("citations"):
            print("FAIL generation: grounded response did not contain validated citations")
            return 1
        agent = client.post(f"{base}/agent/query", headers=headers, json={
            "query": "What is the court name?", "document_version_id": version})
        agent.raise_for_status()
        agent_result = agent.json()
        if agent_result.get("status") != "COMPLETED" or not agent_result.get("citations"):
            print("FAIL agent: synthesis did not complete with validated citations")
            return 1
        checks.extend(["authentication", "upload", "analysis", "retrieval-reranking", "generation", "agent"])
        if second is not None and second.is_file():
            upload2 = client.post(f"{base}/documents", headers=headers, files={
                "file": (second.name, second.read_bytes(), "application/pdf")},
                data={"title": f"smoke-{second.stem}-{uuid.uuid4().hex[:8]}", "document_type": "contract"})
            upload2.raise_for_status()
            version2 = upload2.json()["version_id"]
            client.post(f"{base}/contracts/{version2}/analyze", headers=headers, json={}).raise_for_status()
            comparison = client.post(f"{base}/contracts/compare", headers=headers, json={
                "source_version_id": version, "target_version_id": version2})
            comparison.raise_for_status()
            checks.append("comparison")
    print("PASS " + ", ".join(checks))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except httpx.HTTPError as exc:
        status = getattr(getattr(exc, "response", None), "status_code", "unknown")
        print(f"FAIL HTTP status={status}")
        sys.exit(1)
