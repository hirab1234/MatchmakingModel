"""One-off end-to-end check against the locally running server."""
import json

import httpx

from matchmaking.schemas.examples import MUTUAL_MATCH_EXAMPLE

BASE = "http://127.0.0.1:8001"

# 1) POST /users — send the logged-in user + candidates
# The example keeps Ahmed's preferences top-level; the app's POST /users
# flow expects them embedded in the profile.
logged_in = dict(MUTUAL_MATCH_EXAMPLE["logged_in_user"])
logged_in["partner_preferences"] = MUTUAL_MATCH_EXAMPLE["partner_preferences"]
candidates = MUTUAL_MATCH_EXAMPLE["users"]
payload = {"users": [logged_in] + candidates}

r = httpx.post(f"{BASE}/users", json=payload, timeout=30)
print("POST /users      ->", r.status_code, r.json())

# 2) GET /match/{user_id}
r2 = httpx.get(f"{BASE}/match/user_ahmed", timeout=30)
body = r2.json()
print("GET /match       ->", r2.status_code)
print("  total evaluated:", body.get("total_users_evaluated"))
print("  total matches  :", body.get("total_matches"))
for m in body.get("matches", []):
    print(f"    - {m['candidate_id']:<14} score={m['match_score']:<4} "
          f"status={m['match_status']:<12} level={m['compatibility_level']}")
