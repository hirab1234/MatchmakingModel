"""End-to-end smoke test for a running matchmaking API.

Used by CI against both the ephemeral server started in the test job and the
live deployment, so a green pipeline means the real match flow actually ran.

    python deploy/smoke_test.py http://127.0.0.1:8011
    python deploy/smoke_test.py https://matchmaking.hamqadam.com
"""

from __future__ import annotations

import os
import sys
import time

import httpx

from matchmaking.schemas.examples import MUTUAL_MATCH_EXAMPLE

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8011").rstrip("/")
API_KEY = os.environ.get("MATCHMAKING_API_KEY", "").strip()
HEADERS = {"X-API-Key": API_KEY} if API_KEY else {}

failures: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    print(f"  {'PASS' if condition else 'FAIL'}  {label}{f' — {detail}' if detail else ''}")
    if not condition:
        failures.append(label)


def wait_for_server(timeout: int = 60) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if httpx.get(f"{BASE}/health", timeout=5).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(2)
    print(f"server at {BASE} never became healthy within {timeout}s")
    sys.exit(1)


print(f"Smoke testing {BASE}")
wait_for_server()

# --- health + banner -------------------------------------------------------
health = httpx.get(f"{BASE}/health", timeout=30)
check("GET /health", health.status_code == 200, str(health.json()))
check("GET /", httpx.get(f"{BASE}/", timeout=30).status_code == 200)

# --- upload the user pool --------------------------------------------------
logged_in = dict(MUTUAL_MATCH_EXAMPLE["logged_in_user"])
logged_in["partner_preferences"] = MUTUAL_MATCH_EXAMPLE["partner_preferences"]
payload = {"users": [logged_in] + MUTUAL_MATCH_EXAMPLE["users"]}

upload = httpx.post(f"{BASE}/users", json=payload, headers=HEADERS, timeout=60)
body = upload.json() if upload.status_code == 200 else {}
check("POST /users", upload.status_code == 200 and body.get("total_users") == 5, str(body))

# --- the actual matchmaking ------------------------------------------------
started = time.time()
match = httpx.get(f"{BASE}/match/user_ahmed", headers=HEADERS, timeout=60)
elapsed_ms = (time.time() - started) * 1000
result = match.json() if match.status_code == 200 else {}

check("GET /match/{id}", match.status_code == 200, f"{elapsed_ms:.0f}ms")
check("evaluated all candidates", result.get("total_users_evaluated") == 4)
check("found expected matches", result.get("total_matches") == 3)

ranked = result.get("matches", [])
check("results ranked best-first", [m["match_score"] for m in ranked] == sorted((m["match_score"] for m in ranked), reverse=True))
check("top match is user_fatima", bool(ranked) and ranked[0]["candidate_id"] == "user_fatima")
for m in ranked:
    print(f"        {m['candidate_id']:<14} score={m['match_score']:<4} {m['match_status']:<10} {m['compatibility_level']}")

# --- filters ---------------------------------------------------------------
filtered = httpx.get(f"{BASE}/match/user_ahmed?top_n=2&min_score=80", headers=HEADERS, timeout=60)
check("top_n / min_score filters", filtered.status_code == 200 and len(filtered.json().get("matches", [])) == 2)

# --- error handling --------------------------------------------------------
check("unknown user -> 404", httpx.get(f"{BASE}/match/does_not_exist", headers=HEADERS, timeout=30).status_code == 404)
check("invalid payload -> 422", httpx.post(f"{BASE}/users", json={"users": []}, headers=HEADERS, timeout=30).status_code == 422)

# --- source must not be served through the proxy ---------------------------
if BASE.startswith("https://"):
    leaked = [p for p in ("app.py", "requirements.txt", ".env") if httpx.get(f"{BASE}/{p}", timeout=15).status_code == 200]
    check("source files not exposed", not leaked, f"leaked: {leaked}" if leaked else "")

print()
if failures:
    print(f"SMOKE TEST FAILED — {len(failures)} check(s): {', '.join(failures)}")
    sys.exit(1)
print("SMOKE TEST PASSED — live matchmaking verified end to end")
