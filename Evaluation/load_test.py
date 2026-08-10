"""Concurrent API load test for routes that do not require Gemini."""

from __future__ import annotations

import argparse
import getpass
import json
import os
import time
import urllib.error
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any

from Evaluation.config import OUTPUT_DIR
from Evaluation.performance_report import percentile


def request_json(base_url: str, path: str, *, method: str = "GET",
                 payload: dict | None = None, token: str | None = None,
                 timeout: float = 180) -> tuple[int, dict[str, Any]]:
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}{path}", data=data, headers=headers, method=method
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode()
            return response.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as error:
        body = error.read().decode()
        try:
            return error.code, json.loads(body)
        except json.JSONDecodeError:
            return error.code, {"detail": body}


def summarize(samples: list[dict[str, Any]], wall_seconds: float) -> dict[str, Any]:
    latencies = [float(sample["latency_ms"]) for sample in samples]
    statuses = Counter(str(sample["http_status"]) for sample in samples)
    successful = sum(200 <= int(sample["http_status"]) < 300 for sample in samples)
    return {
        "requests": len(samples), "successful": successful,
        "failed": len(samples) - successful,
        "success_rate": round(successful / len(samples), 4) if samples else 0.0,
        "wall_seconds": round(wall_seconds, 3),
        "throughput_requests_per_second": round(len(samples) / wall_seconds, 3) if wall_seconds else 0.0,
        "latency_ms": ({
            "min": round(min(latencies), 2), "mean": round(mean(latencies), 2),
            "median": round(median(latencies), 2),
            "p95": round(percentile(latencies, 0.95), 2),
            "p99": round(percentile(latencies, 0.99), 2),
            "max": round(max(latencies), 2),
        } if latencies else {}),
        "http_statuses": dict(sorted(statuses.items())),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--mode", choices=("health", "auth", "fast"), default="fast")
    parser.add_argument("--requests", type=int, default=50)
    parser.add_argument("--concurrency", type=int, default=5)
    parser.add_argument("--cleanup", action="store_true")
    parser.add_argument("--output", type=Path, default=OUTPUT_DIR / "load_test_summary.json")
    args = parser.parse_args()
    if args.requests < 1 or args.concurrency < 1:
        raise ValueError("requests and concurrency must be positive")

    token = email = None
    if args.mode != "health":
        email = os.getenv("TEST_USER_EMAIL") or input("Test user email: ").strip()
        password = os.getenv("TEST_USER_PASSWORD") or getpass.getpass("Test user password: ")
        status, login = request_json(
            args.base_url, "/auth/login", method="POST",
            payload={"email": email, "password": password},
        )
        if status != 200 or not login.get("access_token"):
            print(f"Login failed ({status}): {login}")
            return 2
        token = login["access_token"]

    def execute(index: int) -> dict[str, Any]:
        started = time.perf_counter()
        if args.mode == "health":
            status, response = request_json(args.base_url, "/health")
        elif args.mode == "auth":
            status, response = request_json(args.base_url, "/auth/me", token=token)
        else:
            prompt = (
                "I have severe chest pain and difficulty breathing"
                if index % 2 else "hello"
            )
            status, response = request_json(
                args.base_url, "/analysis/text", method="POST",
                payload={"text": prompt, "top_k": 5}, token=token,
            )
        return {
            "index": index, "http_status": status,
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            "session_id": response.get("session_id"),
            "detail": response.get("detail") if status >= 400 else None,
        }

    wall_started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = [pool.submit(execute, index) for index in range(args.requests)]
        samples = [future.result() for future in as_completed(futures)]
    wall_seconds = time.perf_counter() - wall_started

    if args.cleanup and token:
        for session_id in {sample["session_id"] for sample in samples if sample.get("session_id")}:
            request_json(
                args.base_url, f"/upload/session/{session_id}",
                method="DELETE", token=token,
            )

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": args.mode, "base_url": args.base_url,
        "concurrency": args.concurrency,
        **summarize(samples, wall_seconds),
        "limitations": [
            "Fast mode measures deterministic conversation/safety routes and does not call Gemini.",
            "Results describe the current development machine and local database.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"Output: {args.output.resolve()}")
    return 1 if report["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
