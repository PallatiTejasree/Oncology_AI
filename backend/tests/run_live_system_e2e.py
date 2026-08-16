"""Live end-to-end verification for the complete Oncology AI system.

This is intentionally not a unittest: FastAPI, PostgreSQL, ChromaDB, OCR and
the configured Gemini API must be running/available. Test sessions are deleted
at the end; the supplied user account is retained.
"""

from __future__ import annotations

import argparse
import getpass
import json
import mimetypes
import os
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path


class LiveCheckError(RuntimeError):
    pass


def request_json(base_url: str, path: str, *, method: str = "GET", payload=None, token=None):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}{path}", data=data, headers=headers, method=method
    )
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            body = response.read().decode("utf-8")
            return response.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8")
        try:
            return error.code, json.loads(body)
        except json.JSONDecodeError:
            return error.code, {"detail": body}
    except urllib.error.URLError as error:
        raise LiveCheckError(f"Cannot connect to FastAPI: {error.reason}") from error


def request_multipart(base_url: str, path: str, *, email: str, files: list[Path], token: str):
    boundary = f"----OncologyAILive{time.time_ns()}"
    parts = [
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"email\"\r\n\r\n{email}\r\n".encode()
    ]
    for file_path in files:
        mime = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        parts.extend([
            (
                f"--{boundary}\r\nContent-Disposition: form-data; name=\"files\"; "
                f"filename=\"{file_path.name}\"\r\nContent-Type: {mime}\r\n\r\n"
            ).encode(),
            file_path.read_bytes(),
            b"\r\n",
        ])
    parts.append(f"--{boundary}--\r\n".encode())
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}{path}", data=b"".join(parts), method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8")
        try:
            return error.code, json.loads(body)
        except json.JSONDecodeError:
            return error.code, {"detail": body}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise LiveCheckError(message)


def step(number: int, label: str) -> None:
    print(f"\n[{number:02d}] {label}")


def login_with_retry(base_url: str, email: str, password: str) -> tuple[str, str, dict]:
    """Authenticate, allowing interactive correction of stale environment credentials."""
    attempts = 0
    while attempts < 3:
        attempts += 1
        status, login = request_json(
            base_url, "/auth/login", method="POST",
            payload={"email": email, "password": password},
        )
        if status == 200 and login.get("access_token"):
            return email, password, login
        if status != 401 or not sys.stdin.isatty() or attempts >= 3:
            raise LiveCheckError(f"Login failed: {status} {login}")

        print(
            "The test credentials were not accepted. This commonly means the "
            "exported TEST_USER_EMAIL or TEST_USER_PASSWORD is stale."
        )
        email = input("Registered test user email: ").strip()
        password = getpass.getpass("Test user password: ")
        require(bool(email and password), "Email and password are required")
    raise LiveCheckError("Login failed after three attempts")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument(
        "--fixture",
        default="Evaluation/fixtures/oncology_ai_multimodal_test_case.pdf",
        help="Accepted oncology PDF used for the live ingestion test.",
    )
    parser.add_argument("--mismatch-pdf", help="Optional PDF for mismatch-pair verification.")
    parser.add_argument("--mismatch-image", help="Optional image for mismatch-pair verification.")
    parser.add_argument("--allow-gemini-fallback", action="store_true")
    parser.add_argument("--keep-sessions", action="store_true")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[2]
    fixture = Path(args.fixture).expanduser()
    if not fixture.is_absolute():
        fixture = root / fixture
    require(fixture.is_file(), f"Fixture not found: {fixture}")

    email = os.getenv("TEST_USER_EMAIL") or input("Test user email: ").strip()
    password = os.getenv("TEST_USER_PASSWORD") or getpass.getpass("Test user password: ")
    require(bool(email and password), "Email and password are required")

    created_sessions: list[int] = []
    token = None
    try:
        step(1, "FastAPI health")
        status, health = request_json(args.base_url, "/health")
        require(status == 200 and health.get("status") == "healthy", f"Health failed: {status} {health}")
        print("PASS: FastAPI is healthy")

        step(2, "FastAPI → LangChain → Gemini configuration")
        status, connection = request_json(args.base_url, "/analysis/status")
        require(status == 200, f"Status endpoint failed: {status} {connection}")
        require(connection.get("connected") is True, f"LangChain is not connected: {connection}")
        require(connection.get("gemini_configured") is True, f"Gemini key is not configured: {connection}")
        require(connection.get("ready") is True, f"Analysis service is not ready: {connection}")
        print(f"PASS: {connection.get('orchestrator')} / {connection.get('gemini_model')} ready")

        step(3, "Login and JWT authentication")
        email, password, login = login_with_retry(args.base_url, email, password)
        token = login["access_token"]
        status, account = request_json(args.base_url, "/auth/me", token=token)
        require(status == 200 and account.get("email") == email, f"JWT validation failed: {status} {account}")
        print("PASS: authenticated account verified")

        step(4, "PostgreSQL quick-response and saved conversation")
        status, greeting = request_json(
            args.base_url, "/analysis/text", method="POST",
            payload={"text": "hello", "top_k": 5}, token=token,
        )
        require(status == 200 and greeting.get("response_type") == "conversation", f"Greeting failed: {status} {greeting}")
        greeting_session = greeting.get("session_id")
        require(bool(greeting_session), "Greeting response did not create a session")
        created_sessions.append(greeting_session)
        status, saved = request_json(args.base_url, f"/upload/session/{greeting_session}", token=token)
        require(status == 200 and saved.get("latest_summary"), "Greeting was not reopened from PostgreSQL")
        print("PASS: database-managed response persisted")

        step(5, "Oncology PDF upload")
        status, upload = request_multipart(
            args.base_url, "/upload", email=email, files=[fixture], token=token
        )
        require(status == 200 and upload.get("session_id"), f"Upload failed: {status} {upload}")
        analysis_session = upload["session_id"]
        upload_ingestion = upload.get("ingestion") or {}
        created_sessions.append(analysis_session)
        require(
            upload_ingestion.get("text_chunks", 0) > 0,
            f"Upload-time ingestion did not index text chunks: {upload_ingestion}",
        )
        print(
            f"PASS: uploaded and indexed into session {analysis_session} "
            f"(chunks={upload_ingestion.get('text_chunks')})"
        )

        step(6, "Ingestion → chunks/embeddings → Chroma → LangChain → Gemini")
        status, result = request_json(
            args.base_url, f"/analysis/session/{analysis_session}", method="POST",
            payload={"question": "Summarize this oncology report in simple language.", "top_k": 5},
            token=token,
        )
        require(status == 200 and str(result.get("summary") or "").strip(), f"Analysis failed: {status} {result}")
        ingestion = (result.get("diagnostics") or {}).get("upload_ingestion") or {}
        private = (result.get("diagnostics") or {}).get("private_upload_retrieval") or {}
        # With the current architecture ingestion runs in the Upload API. The
        # Analysis API invokes the idempotent ingestion guard, which correctly
        # reports zero *new* chunks for an already-indexed report.
        indexed_chunks = upload_ingestion.get("text_chunks", 0) + ingestion.get("text_chunks", 0)
        require(indexed_chunks > 0, f"No text chunks were indexed: upload={upload_ingestion} analysis={ingestion}")
        require(private.get("ownership_filter") == "user_id_and_session_id", f"Private retrieval filter missing: {private}")
        if not args.allow_gemini_fallback:
            require(result.get("model_name") != "retrieval-only", f"Gemini fell back to retrieval-only: {result.get('generation_diagnostics')}")
        print(f"PASS: chunks={indexed_chunks} model={result.get('model_name')}")

        step(7, "PostgreSQL result/history reopen")
        status, saved = request_json(args.base_url, f"/upload/session/{analysis_session}", token=token)
        require(status == 200 and saved.get("latest_summary"), "Generated result was not saved in PostgreSQL")
        status, history = request_json(args.base_url, f"/upload/history/{email}", token=token)
        require(status == 200 and any(item.get("session_id") == analysis_session for item in history), "Session missing from history")
        print("PASS: analysis is present in history")

        step(8, "Rename, archive and restore")
        status, renamed = request_json(
            args.base_url, f"/upload/session/{analysis_session}/name", method="PATCH",
            payload={"name": "Live E2E Oncology Report"}, token=token,
        )
        require(status == 200 and renamed.get("name") == "Live E2E Oncology Report", f"Rename failed: {status} {renamed}")
        status, archived = request_json(args.base_url, f"/upload/session/{analysis_session}/archive", method="PATCH", token=token)
        require(status == 200, f"Archive failed: {status} {archived}")
        status, archive = request_json(args.base_url, "/upload/archive", token=token)
        require(status == 200 and any(item.get("session_id") == analysis_session for item in archive), "Archived session missing")
        status, restored = request_json(args.base_url, f"/upload/session/{analysis_session}/restore", method="PATCH", token=token)
        require(status == 200, f"Restore failed: {status} {restored}")
        print("PASS: rename/archive/restore persisted")

        step(9, "Rejected blank image retention")
        with tempfile.TemporaryDirectory() as temp_dir:
            from PIL import Image
            blank = Path(temp_dir) / "live_blank.png"
            Image.new("RGB", (300, 300), "white").save(blank)
            status, blank_upload = request_multipart(
                args.base_url, "/upload", email=email, files=[blank], token=token
            )
            require(status == 200 and blank_upload.get("session_id"), f"Blank upload setup failed: {status} {blank_upload}")
            blank_session = blank_upload["session_id"]
            created_sessions.append(blank_session)
            status, rejected_analysis = request_json(
                args.base_url, f"/analysis/session/{blank_session}", method="POST",
                payload={"question": "Analyze this image", "top_k": 5}, token=token,
            )
            require(status == 422, f"Blank image should be rejected, received {status}: {rejected_analysis}")
            status, rejected = request_json(args.base_url, "/upload/rejected", token=token)
            require(status == 200 and any(item.get("session_id") == blank_session for item in rejected), "Rejected file was not retained/listed")
        print("PASS: blank image and rejection reason retained")

        mismatch_pdf = Path(args.mismatch_pdf).expanduser() if args.mismatch_pdf else None
        mismatch_image = Path(args.mismatch_image).expanduser() if args.mismatch_image else None
        if mismatch_pdf and mismatch_image:
            step(10, "Multimodal mismatch rejection")
            require(mismatch_pdf.is_file() and mismatch_image.is_file(), "Mismatch fixture path is invalid")
            status, mismatch_upload = request_multipart(
                args.base_url, "/upload", email=email,
                files=[mismatch_pdf, mismatch_image], token=token,
            )
            require(status == 200 and mismatch_upload.get("session_id"), f"Mismatch upload failed: {status} {mismatch_upload}")
            mismatch_session = mismatch_upload["session_id"]
            created_sessions.append(mismatch_session)
            status, mismatch = request_json(
                args.base_url, f"/analysis/session/{mismatch_session}", method="POST",
                payload={"question": "Tell me about these files", "top_k": 5}, token=token,
            )
            require(status == 200 and mismatch.get("response_type") == "rejection", f"Mismatch was not rejected: {status} {mismatch}")
            require((mismatch.get("diagnostics") or {}).get("upload_consistency", {}).get("status") == "mismatch", "Mismatch diagnostics missing")
            print("PASS: different-case files stopped before Gemini")
        else:
            print("\n[10] Multimodal mismatch rejection\nSKIP: provide --mismatch-pdf and --mismatch-image to run this optional check")

        print("\nLIVE E2E RESULT: PASS")
        return 0
    except LiveCheckError as error:
        print(f"\nLIVE E2E RESULT: FAIL\n{error}", file=sys.stderr)
        return 1
    finally:
        if token and not args.keep_sessions:
            print("\n[CLEANUP] Deleting test sessions, files and private vectors")
            for session_id in reversed(created_sessions):
                status, response = request_json(
                    args.base_url, f"/upload/session/{session_id}", method="DELETE", token=token
                )
                if status == 200:
                    verify_status, _ = request_json(
                        args.base_url, f"/upload/session/{session_id}", token=token
                    )
                    print(f"session {session_id}: {'deleted' if verify_status == 404 else 'delete verification failed'}")
                else:
                    print(f"session {session_id}: cleanup failed ({status}) {response}")


if __name__ == "__main__":
    raise SystemExit(main())
