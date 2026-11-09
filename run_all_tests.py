"""CLI test suite sharing the same client/evidence layer as the web interface.

Safe default: python run_all_tests.py --mode dry-run
Negative checks: python run_all_tests.py --mode negative
All SIX paid analysis submissions: python run_all_tests.py --mode full --confirm-credits
One analysis: python run_all_tests.py --mode one --endpoint env_params --confirm-credits
"""
from __future__ import annotations

import argparse
import getpass
import json
import sys
from typing import Any

from fortyguard_client import (
    ENDPOINTS, TOTAL_ESTIMATED_CREDITS, activity_id_from, api_call,
    default_payload, record_evidence, sanitized_result, submit,
)


def print_result(title: str, http: int | None, body: dict, endpoint: str, method: str,
                 request: dict | None = None, cost: int = 0) -> None:
    evidence = record_evidence(title, method, endpoint, request, http, body, estimate=cost)
    print(f"\n[{title}] HTTP={http if http is not None else 'TRANSPORT ERROR'}")
    activity = activity_id_from(body)
    if activity:
        print(f"  Activity ID: {activity}")
    if body.get("error"):
        details = body.get("details") or {}
        print(f"  Error: {body.get('message') or (details.get('message') if isinstance(details, dict) else '')}")
        if body.get("code"):
            print(f"  Error code: {body['code']}")
    print(f"  Evidence: {evidence}")


def negative_tests(api_key: str) -> None:
    print("Running three non-billable validation/authentication checks")
    test_cases = [
        ("Missing API key", "POST", "/v1/heatmap", None, {}),
        ("Missing required fields", "POST", "/v1/heatmap", api_key, {}),
        ("Unknown activity ID", "GET", "/v1/status/00000000-0000-4000-8000-000000000000", api_key, None),
    ]
    for name, method, endpoint, key, payload in test_cases:
        code, body = api_call(method, endpoint, api_key=key, payload=payload)
        print_result(name, code, body, endpoint, method, payload)


def live_test(name: str, api_key: str) -> None:
    config = ENDPOINTS[name]
    payload = default_payload(name)
    code, body = submit(name, api_key, payload)
    print_result(f"submit_{name}", code, body, config["path"], "POST", payload, config["credits"])
    if code is not None and 200 <= code < 300:
        print("  Submission accepted. Check task completion separately in the web UI.")
    else:
        print("  Submission not accepted. No activity status is implied.")


def main() -> None:
    parser = argparse.ArgumentParser(description="FortyGuard evaluation test runner")
    parser.add_argument("--mode", choices=["dry-run", "negative", "one", "full"], default="dry-run")
    parser.add_argument("--endpoint", choices=list(ENDPOINTS))
    parser.add_argument("--confirm-credits", action="store_true", help="Explicit consent to billable live analysis requests")
    args = parser.parse_args()

    if args.mode == "dry-run":
        print("NO NETWORK REQUESTS WILL BE MADE in dry-run mode.")
        for k, config in ENDPOINTS.items():
            print(f"  POST {config['path']:<24} {config['title']:<29} ~{config['credits']:,} credits if completed")
        print(f"Total for one completed submission per service: ~{TOTAL_ESTIMATED_CREDITS:,} Premium credits")
        print("\nRun --mode negative for error checks, or --mode one --endpoint env_params --confirm-credits")
        return
    if args.mode in ("full", "one"):
        if not args.confirm_credits:
            parser.error("Live analysis requests require --confirm-credits")
        if args.mode == "one" and not args.endpoint:
            parser.error("--mode one requires --endpoint")
        print(f"CAUTION: credits are deducted on successful completion; full-suite maximum published cost ~{TOTAL_ESTIMATED_CREDITS:,} credits")
    key = getpass.getpass("FortyGuard API key (hidden): ").strip()
    if not key:
        parser.error("API key was empty")
    if args.mode == "negative":
        negative_tests(key)
    elif args.mode == "one":
        live_test(args.endpoint, key)
    elif args.mode == "full":
        for name in ENDPOINTS:
            live_test(name, key)
        print("\nSix submissions attempted. Poll activity IDs manually. No requests will auto-repeat.")


if __name__ == "__main__":
    main()
