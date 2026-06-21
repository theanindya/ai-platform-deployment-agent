import json
import httpx
import time

BASE_URL = "http://127.0.0.1:8000"

scenarios = [
    "req_001_standard",
    "req_002_critical_cve",
    "req_003_poor_metrics"
]

print("Starting endpoint verification tests...")

# Wait briefly for server to boot up
time.sleep(2)

with httpx.Client(timeout=30.0) as client:
    for scenario in scenarios:
        print(f"\n--- Testing Scenario: {scenario} ---")
        try:
            with open(f"data/deployment_requests/{scenario}.json", "r") as f:
                payload = json.load(f)
            
            resp = client.post(f"{BASE_URL}/deploy", json=payload)
            if resp.status_code != 200:
                print(f"Error: {resp.status_code} - {resp.text}")
                continue
                
            data = resp.json()
            print(f"Request ID: {data.get('request_id')}")
            print(f"Verdict   : {data.get('verdict')}")
            print(f"Reason    : {data.get('reason')}")
            print(f"Risk Score: {data.get('risk_assessment', {}).get('risk_score')}")
            print(f"Risk Level: {data.get('risk_assessment', {}).get('risk_level')}")
            print(f"Violations: {data.get('violations')}")
        except Exception as e:
            print(f"Failed to verify: {e}")
