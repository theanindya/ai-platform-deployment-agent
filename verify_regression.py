"""
Regression verification script.
Sends all three deployment JSON fixtures to POST /deploy
and asserts all required response fields are present and correct.
"""
import asyncio
import json
import os
import sys
import time
import httpx

BASE_URL = "http://localhost:8000"

SCENARIOS = [
    {
        "file": "req_001_standard.json",
        "expected_verdict": "APPROVED",
        "label": "Scenario 1 — Standard Production (APPROVED)",
    },
    {
        "file": "req_002_critical_cve.json",
        "expected_verdict": "BLOCKED",
        "label": "Scenario 2 — Critical CVE (BLOCKED)",
    },
    {
        "file": "req_003_poor_metrics.json",
        "expected_verdict_in": ["APPROVED WITH WARNINGS", "BLOCKED"],
        "label": "Scenario 3 — Poor Metrics (APPROVED WITH WARNINGS)",
    },
]

REQUIRED_FIELDS = [
    "verdict",
    "reason",
    "violations",
    "risk_assessment",
    "decision_confidence",
    "agents_invoked",
    "mcp_calls_made",
]

DATA_DIR = os.path.join(os.path.dirname(__file__), "data", "deployment_requests")

PASS = "[PASS]"
FAIL = "[FAIL]"
SEP  = "-" * 70


def load_req(filename):
    with open(os.path.join(DATA_DIR, filename)) as f:
        return json.load(f)


def check_field(label, value, ok):
    mark = PASS if ok else FAIL
    print(f"    {mark}  {label}: {value}")
    return ok


async def verify_scenario(client, scenario):
    print(f"\n{SEP}")
    print(f"  {scenario['label']}")
    print(SEP)

    payload = load_req(scenario["file"])
    try:
        resp = await client.post("/deploy", json=payload, timeout=60.0)
        resp.raise_for_status()
    except Exception as e:
        print(f"  {FAIL}  Request failed: {e}")
        return False

    data = resp.json()
    all_ok = True

    # Check all required fields present
    print("  Required fields:")
    for field in REQUIRED_FIELDS:
        present = field in data
        all_ok = check_field(f"  {field}", "(present)" if present else "MISSING", present) and all_ok

    print("\n  Values:")
    # verdict
    verdict = data.get("verdict", "")
    if "expected_verdict" in scenario:
        ok = verdict == scenario["expected_verdict"]
    else:
        ok = verdict in scenario["expected_verdict_in"]
    all_ok = check_field("verdict", verdict, ok) and all_ok

    # reason
    reason = data.get("reason", "")
    all_ok = check_field("reason", reason[:80] + "..." if len(reason) > 80 else reason, bool(reason)) and all_ok

    # risk_assessment
    ra = data.get("risk_assessment", {})
    all_ok = check_field("risk_score", ra.get("risk_score"), ra.get("risk_score") is not None) and all_ok
    all_ok = check_field("risk_level", ra.get("risk_level"), bool(ra.get("risk_level"))) and all_ok

    # decision_confidence
    dc = data.get("decision_confidence")
    all_ok = check_field("decision_confidence", dc, dc is not None and 0.0 <= dc <= 1.0) and all_ok

    # agents_invoked
    ai = data.get("agents_invoked", [])
    all_ok = check_field("agents_invoked", f"{len(ai)} agents", len(ai) == 5) and all_ok

    # mcp_calls_made
    mc = data.get("mcp_calls_made")
    all_ok = check_field("mcp_calls_made", mc, mc is not None and mc >= 4) and all_ok

    # violations list
    viol = data.get("violations", [])
    check_field("violations count", len(viol), True)

    # policy_reasoning
    pr = data.get("policy_reasoning", "")
    check_field("policy_reasoning", pr, pr in ("rule-based", "gemini-2.0-flash"))

    print(f"\n  {'PASS' if all_ok else 'FAIL'} — {scenario['label']}")
    return all_ok


async def main():
    # Wait briefly for server to be ready
    print("Waiting for server...")
    for _ in range(15):
        try:
            async with httpx.AsyncClient(base_url=BASE_URL) as c:
                await c.get("/docs", timeout=2)
            break
        except Exception:
            time.sleep(1)
    else:
        print(f"{FAIL} Server not reachable at {BASE_URL}")
        sys.exit(1)

    print(f"\n{PASS} Server is up at {BASE_URL}")

    results = []
    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        for scenario in SCENARIOS:
            ok = await verify_scenario(client, scenario)
            results.append(ok)

    print(f"\n{SEP}")
    passed = sum(results)
    total  = len(results)
    status = PASS if passed == total else FAIL
    print(f"  {status}  {passed}/{total} scenarios passed")
    print(SEP)

    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    asyncio.run(main())
