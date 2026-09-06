# AI Matchmaking Model — Documentation

## Architecture

```
Backend
   |
   | Partner Preferences + User/Candidate Data
   ↓
MatchMakingAiModel (MatchmakingService)
   |
   | Validate → Normalize → Process
   ↓
Processing / Matchmaking Engine
   |
   | Apply preferences, rules, scoring,
   | compatibility logic and AI reasoning
   ↓
AiMatchMakingModel
   |
   | Generate structured matchmaking result
   ↓
Response (MatchmakingResponse)
   |
   ↓
Backend
```

### Responsibility Boundary

```
┌────────────────────────────────┐
│           BACKEND              │
│                                │
│ • User/Candidate Data          │
│ • Partner Preferences          │
│ • Database                     │
│ • Authentication               │
│ • Business Transactions        │
└──────────────┬─────────────────┘
               │
               │ Input (MatchmakingRequest)
               ▼
┌────────────────────────────────┐
│     MATCH MAKING AI MODEL      │
│                                │
│ • Input Validation             │
│ • Data Normalization           │
│ • Preference Classification    │
│ • Hard Constraint Checking     │
│ • Deal Breaker Detection       │
│ • Criterion Scoring            │
│ • Weighted Compatibility       │
│ • AI Enhancement               │
│ • Explainability               │
│ • Response Formatting          │
└──────────────┬─────────────────┘
               │
               │ Output (MatchmakingResponse)
               ▼
┌────────────────────────────────┐
│           BACKEND              │
│                                │
│ • Persistence                  │
│ • Business Decisions           │
│ • Frontend Communication       │
└────────────────────────────────┘
```

**The AI model:**
- Does NOT access any database
- Does NOT fetch user data
- Does NOT modify backend data
- Receives all data FROM the backend
- Returns structured results TO the backend

---

## Input Contract

### MatchmakingRequest

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `request_id` | `string` | Auto-generated | Unique request ID for tracking |
| `user` | `UserProfile` | **Yes** | The user seeking a partner |
| `partner_preferences` | `PartnerPreferences` | **Yes** | What the user wants in a partner |
| `candidate` | `UserProfile` | One of `candidate`/`candidates` | Single candidate to evaluate |
| `candidates` | `List[UserProfile]` | One of `candidate`/`candidates` | Multiple candidates to rank |
| `context` | `MatchContext` | No | Additional context (source, priority, metadata) |

### UserProfile

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `user_id` | `string` | **Yes** (min 1 char) | Unique identifier |
| `gender` | `enum` | No | `male`, `female`, `other` |
| `date_of_birth` | `date` | No | Used to compute age if `age` not provided |
| `age` | `int` | No | 18-120 |
| `height_cm` | `int` | No | 100-250 |
| `marital_status` | `enum` | No | `never_married`, `divorced`, `widowed`, etc. |
| `mother_tongue` | `string` | No | e.g., "Urdu" |
| `religion` | `string` | No | e.g., "Islam" |
| `sect` | `string` | No | e.g., "Sunni" |
| `education` | `enum` | No | `high_school`, `bachelors`, `masters`, `doctorate`, etc. |
| `profession` | `string` | No | e.g., "Software Engineer" |
| `profession_category` | `string` | No | e.g., "Technology" |
| `location` | `Location` | No | `{city, country, state}` |
| `interests` | `List[string]` | No | e.g., `["Travel", "Reading"]` |
| `hobbies` | `List[string]` | No | e.g., `["Hiking", "Chess"]` |
| `personality_traits` | `List[string]` | No | e.g., `["Introverted", "Analytical"]` |
| `lifestyle` | `Dict[string, any]` | No | e.g., `{"exercise": "regular"}` |
| `smoking` | `bool` | No | `true`/`false` |
| `drinking` | `bool` | No | `true`/`false` |
| `diet` | `string` | No | e.g., "Halal" |
| `about_me` | `string` | No | Free text |
| `family_details` | `Dict[string, any]` | No | Family information |

### PartnerPreferences

All 25 preferences from section 17 of the product document are supported.
Every field is optional, and **an omitted preference is not scored at all** —
it is excluded from the weighted average rather than counted as a neutral 50.

| # | Field | Type | Description |
|---|-------|------|-------------|
| 1 | `age_range` | `{min, max}` | Preferred age range |
| 2 | `height_range` | `{min_cm, max_cm}` | Preferred height range |
| 3 | `location` | `List[string]` | Preferred cities |
| 4 | `country` | `List[string]` | Preferred countries |
| 5 | `marital_status` | `List[enum]` | Acceptable marital statuses |
| 6 | `religion` | `List[string]` | Acceptable religions |
| 7 | `sect` | `List[string]` | Acceptable sects |
| 8 | `religious_practice` | `List[enum]` | `not_practicing` … `very_practicing` |
| 9 | `min_education` | `enum` | Minimum acceptable education level |
| 10 | `preferred_field` | `List[string]` | Preferred field of study |
| 11 | `profession` / `profession_category` | `List[string]` | Preferred professions |
| 12 | `employment_status` | `List[enum]` | `employed`, `self_employed`, `business_owner`, … |
| 13 | `income_range` | `{min, max, currency}` or `string` | Preferred monthly income band |
| 14 | `family_structure` | `List[enum]` | `nuclear`, `joint`, `extended`, `single_parent` |
| 15 | `living_arrangement` | `List[enum]` | `with_parents`, `separate_house`, `independent`, `abroad`, `flexible` |
| 16 | `family_involvement` | `List[enum]` | `minimal`, `low`, `moderate`, `high` |
| 17 | `smoking` | `bool` | `false` = non-smoker required |
| 18 | `diet` | `List[string]` | e.g. `["Halal"]` |
| 19 | `exercise` | `List[enum]` | `never` … `daily` |
| 20 | `social_lifestyle` | `List[enum]` | `homebody` … `very_social` |
| 21 | `personality_traits` | `List[string]` | Desired traits |
| 22 | `marriage_timeline` | `List[enum]` | `immediately` … `no_rush` |
| 23 | `children_preference` | `List[enum]` | `want_children`, `dont_want_children`, … |
| 24 | `relocation` | `List[enum]` | `willing`, `negotiable`, `within_country_only`, `not_willing` |
| 25 | `career_expectation` | `List[enum]` | `continue_career`, `part_time`, `flexible`, `stop_after_marriage` |

Also supported:

| Field | Type | Description |
|-------|------|-------------|
| `gender` | `enum` | Preferred partner gender (hard constraint) |
| `education` | `List[enum]` | Explicit allow-list of education levels |
| `mother_tongue` | `List[string]` | Acceptable languages |
| `interests` / `hobbies` | `List[string]` | Desired shared interests |
| `drinking` | `bool` | `false` = non-drinker required |
| `lifestyle` | `Dict[string, any]` | Free-form lifestyle attributes |
| `deal_breakers` | `List[string]` | Absolute disqualifiers |
| `hard_constraints` | `Dict[string, any]` | Additional hard constraints |
| `soft_preferences` | `Dict[string, any]` | Additional soft preferences |

**Ordinal vs categorical scoring.** Fields that sit on a spectrum
(`religious_practice`, `exercise`, `social_lifestyle`, `family_involvement`,
`marriage_timeline`, `education`) award partial credit for being *close* to
what was asked for. Categorical fields either match, are "open-ended"
(e.g. `flexible`, `open_to_children`) and score partial, or clash outright —
`dont_want_children` against `want_children` scores 0, not 25.

---

## Output Contract

### MatchmakingResponse

| Field | Type | Description |
|-------|------|-------------|
| `success` | `bool` | Whether processing succeeded |
| `model_version` | `string` | Model version that generated the result |
| `request_id` | `string` | Echo of the request ID |
| `processing_time_ms` | `float` | Processing duration in milliseconds |
| `result` | `CandidateMatchResult` | Single candidate result (if single candidate request) |
| `results` | `List[CandidateMatchResult]` | Ranked results (if multi-candidate request) |
| `error` | `Dict` | Error details (if `success=false`) |

### CandidateMatchResult

| Field | Type | Description |
|-------|------|-------------|
| `candidate_id` | `string` | The candidate's user ID |
| `is_match` | `bool` | Whether this qualifies as a match |
| `match_score` | `int` (0-100) | Overall compatibility score |
| `compatibility_level` | `enum` | `very_high`, `high`, `medium`, `low`, `very_low`, `none` |
| `match_status` | `enum` | `match`, `partial_match`, `no_match`, `unknown`, `rejected` |
| `criterion_matches` | `List[CriterionMatch]` | Per-criterion scoring breakdown |
| `matched_preferences` | `List[string]` | Fully satisfied preferences |
| `partial_matches` | `List[string]` | Partially satisfied preferences |
| `mismatched_preferences` | `List[string]` | Unsatisfied preferences |
| `deal_breakers_violated` | `List[string]` | Violated deal breakers |
| `match_reasons` | `List[string]` | Why they match (or don't) |
| `concerns` | `List[string]` | Potential issues |
| `recommendations` | `List[string]` | Actionable suggestions |
| `confidence_score` | `int` (0-100) | Model confidence in assessment |
| `processing_time_ms` | `float` | Per-candidate processing time |
| `ai_enhanced` | `bool` | Whether AI reasoning was applied |

---

## Mutual (Two-Way) Matchmaking

`POST /matchmaking/match-users`

This is the endpoint the app calls to build a logged-in user's match list.

A one-way score is not enough: a candidate who perfectly fits what the
logged-in user wants may be looking for something completely different. This
endpoint therefore scores **both directions** and combines them.

```
direction 1  your_preferences_match   (user_to_candidate)
             logged-in user's preferences  ->  candidate's profile
             "Does this person match what I am looking for?"

direction 2  their_preferences_match  (candidate_to_user)
             candidate's preferences  ->  logged-in user's profile
             "Am I what this person is looking for?"

mutual score = d1 x user_preference_weight
             + d2 x candidate_preference_weight
             - one-sidedness penalty
```

### Request

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `logged_in_user` | `UserProfile` | Yes | The signed-in user |
| `partner_preferences` | `PartnerPreferences` | Yes* | What they are looking for |
| `users` | `List[UserProfile]` | Yes | The users appearing in the list |
| `top_n` | `int` | No | Return only the top N matches |
| `min_score` | `int` | No | Drop results below this mutual score |
| `include_criterion_breakdown` | `bool` | No | Default `true` |

\* May instead be supplied as `logged_in_user.partner_preferences`. The
top-level field wins when both are present.

Each entry in `users` should carry its **own** `partner_preferences`. That is
what makes direction 2 possible.

### Response

Each entry of `matches` contains:

| Field | Description |
|-------|-------------|
| `match_score` / `match_percentage` | Mutual compatibility, 0-100 |
| `compatibility_level` | `very_high` … `none` |
| `match_status` | `match`, `partial_match`, `no_match`, `rejected` |
| `model_confidence` | `low` / `medium` / `high` (document requirement) |
| `confidence_score` | Numeric confidence behind that bucket |
| `your_preferences_match` | Full direction-1 result incl. per-criterion breakdown |
| `their_preferences_match` | Full direction-2 result |
| `mutual_matched_preferences` | Criteria satisfied in **both** directions |
| `one_sided_preferences` | Criteria satisfied in only one direction |
| `score_balance` | `abs(d1 - d2)` — high means one-sided interest |
| `match_reasons` / `concerns` / `recommendations` | Explainability |

Results are sorted by mutual score descending, then by confidence.

### Rules

- **Rejection is symmetric.** A deal breaker or failed hard constraint on
  *either* side sets `match_status: "rejected"` and `is_match: false`,
  regardless of the numeric score.
- **One-way fallback.** If a listed user has no `partner_preferences`, only
  direction 1 is scored, `their_preferences_match.evaluated` is `false`, the
  confidence is capped at 75% of its normal value, and the response carries a
  warning naming that user.
- **One-sidedness penalty.** When the two directions differ by more than
  `mutual_balance_gap_threshold` (default 30), up to
  `mutual_balance_max_penalty` (default 8) points are deducted — a pairing that
  only works in one direction is not a good match.
- **Self-exclusion.** The logged-in user is skipped if present in `users`.
- This endpoint is fully deterministic; it does not call the AI provider, so
  scoring a list stays fast and reproducible.

### Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `USER_PREFERENCE_WEIGHT` | 0.6 | Weight of direction 1 |
| `CANDIDATE_PREFERENCE_WEIGHT` | 0.4 | Weight of direction 2 |
| `MUTUAL_BALANCE_PENALTY_ENABLED` | true | Penalise one-sided pairings |
| `MUTUAL_BALANCE_GAP_THRESHOLD` | 30 | Gap at which the penalty starts |
| `MUTUAL_BALANCE_MAX_PENALTY` | 8.0 | Maximum points deducted |
| `CONFIDENCE_HIGH_THRESHOLD` | 75 | Confidence >= this = `high` |
| `CONFIDENCE_MEDIUM_THRESHOLD` | 50 | Confidence >= this = `medium` |

### Example

Swagger UI pre-fills a complete, runnable example at `/docs` — one logged-in
user with all 25 preferences set, and four users who each have their own
preferences. Executing it returns:

| Candidate | You -> them | They -> you | Mutual | Status |
|-----------|------------|-------------|--------|--------|
| Fatima Ali | 96% | 95% | **96%** | match (very_high, confidence high) |
| Zara Sheikh | 94% | 95% | **94%** | match (very_high, confidence high) |
| Ayesha Malik | 70% | 82% | **75%** | match (high) |
| Sana Rehman | 0% | 8% | **3%** | rejected — sect and marital status fail both ways |

---

## Scoring System

### Formula

```
Overall Score = Σ(criterion_score × weight) / Σ(weight)
                    ...over APPLICABLE criteria only
```

A criterion is **applicable** only when the user actually expressed that
preference. Criteria the user left blank are dropped from both the numerator
and the denominator, so a sparsely filled preference form no longer pulls every
result towards 50%. Each `CriterionMatch` carries an `applicable` flag, and
only applicable criteria are returned in the response breakdown.

If the candidate has the preference but has not filled in that field, the
criterion stays applicable and scores the neutral `missing_data_score` (50),
which also lowers the confidence.

Score range: **0** (no compatibility) to **100** (perfect compatibility)

### Configurable Weights

Defaults sum to 1.0 across all 28 criteria.

| Criterion | Weight | | Criterion | Weight |
|-----------|--------|-|-----------|--------|
| `location` | 0.10 | | `family_structure` | 0.03 |
| `religion` | 0.09 | | `height` | 0.02 |
| `age` | 0.06 | | `mother_tongue` | 0.02 |
| `sect` | 0.05 | | `education_field` | 0.02 |
| `religious_practice` | 0.05 | | `living_arrangement` | 0.02 |
| `education` | 0.05 | | `family_involvement` | 0.02 |
| `personality` | 0.05 | | `smoking` | 0.02 |
| `interests` | 0.05 | | `diet` | 0.02 |
| `children_preference` | 0.05 | | `exercise` | 0.02 |
| `marital_status` | 0.04 | | `social_lifestyle` | 0.02 |
| `profession` | 0.04 | | `relocation` | 0.02 |
| `marriage_timeline` | 0.04 | | `career_expectation` | 0.02 |
| `employment_status` | 0.03 | | `drinking` | 0.01 |
| `income` | 0.03 | | `lifestyle` | 0.01 |

Override via environment variables:
```
SCORING_WEIGHT_AGE=0.15
SCORING_WEIGHT_LOCATION=0.20
```

### Hard Constraints vs Soft Preferences

**Hard Constraints** (failure = rejection or major penalty):
- `gender`, `religion`, `sect`, `marital_status`
- Custom `hard_constraints` from preferences

**Soft Preferences** (failure = score reduction):
- Every other preference field, i.e. all of the 25 document fields that are
  not listed as hard constraints above.

**Deal Breakers** (violation = immediate rejection):
- Defined in `deal_breakers` list
- Examples: `smoking`, `drinking`, `divorced`

### Thresholds

| Threshold | Default | Description |
|-----------|---------|-------------|
| `match_threshold` | 70 | Score >= this = `is_match: true` |
| `high_compatibility` | 85 | Score >= this = `very_high` |
| `medium_compatibility` | 60 | Score >= this = `medium` |
| `low_compatibility` | 40 | Score >= this = `low` |

---

## AI Enhancement

### Where AI is Used

- **Semantic interest similarity** — understands conceptually related interests
- **Personality compatibility analysis** — beyond keyword matching
- **Contextual reasoning** — cultural and relationship insights
- **Explanation generation** — human-readable insights

### Where Deterministic Logic is Used

- Hard constraint evaluation (gender, religion, etc.)
- Deal breaker detection
- Age/height range scoring
- Education level comparison
- Location matching
- All critical business rules

### AI Safety Rules

1. AI never overrides hard constraints or deal breakers
2. AI enhances scores but doesn't replace deterministic scoring
3. AI output is validated against a schema
4. AI failures fall back to deterministic results
5. AI is optional (can be disabled via `AI_ENABLED=false`)

### AI Configuration

```
AI_ENABLED=true
AI_PROVIDER=openai
AI_MODEL=gpt-4o
AI_TEMPERATURE=0.1
AI_TIMEOUT=30
```

---

## Error Handling

| Error Code | HTTP Status | Description |
|------------|-------------|-------------|
| `INPUT_VALIDATION_ERROR` | 422 | Malformed or invalid input |
| `AI_PROVIDER_ERROR` | 500 | AI provider failure |
| `AI_RESPONSE_VALIDATION_ERROR` | 500 | AI returned invalid output |
| `PROCESSING_TIMEOUT` | 500 | Processing exceeded time limit |
| `INTERNAL_ERROR` | 500 | Unexpected error |

All errors return structured JSON without exposing internal details.

---

## Integration Guide

### HTTP Integration (FastAPI)

```python
import httpx

response = httpx.post(
    "http://localhost:8000/matchmaking/process",
    json={
        "request_id": "req_001",
        "user": {
            "user_id": "user_123",
            "gender": "female",
            "age": 30,
            "religion": "Islam",
            "education": "masters",
            "location": {"city": "Islamabad", "country": "Pakistan"},
            "interests": ["Reading", "Travel"]
        },
        "partner_preferences": {
            "gender": "male",
            "age_range": {"min": 28, "max": 40},
            "religion": ["Islam"],
            "education": ["masters", "doctorate"],
            "location": ["Islamabad"],
            "interests": ["Reading", "Technology"],
            "deal_breakers": ["smoking"]
        },
        "candidate": {
            "user_id": "candidate_456",
            "gender": "male",
            "age": 33,
            "religion": "Islam",
            "education": "masters",
            "location": {"city": "Islamabad", "country": "Pakistan"},
            "interests": ["Reading", "Travel", "Technology"]
        }
    }
)
result = response.json()
```

### Python Direct Integration

```python
from matchmaking.config import MatchmakingConfig
from matchmaking.schemas import MatchmakingRequest, UserProfile, PartnerPreferences
from matchmaking.services import MatchmakingService

# Create service (AI disabled for direct integration)
config = MatchmakingConfig(ai_enabled=False)
service = MatchmakingService(config)

# Build request
request = MatchmakingRequest(
    user=UserProfile(user_id="u1", gender="female", age=30, religion="Islam"),
    partner_preferences=PartnerPreferences(
        gender="male",
        religion=["Islam"],
        age_range={"min": 28, "max": 40},
    ),
    candidate=UserProfile(user_id="c1", gender="male", age=33, religion="Islam"),
)

# Process
response = service.process(request)

# Use result
if response.success:
    print(f"Score: {response.result.match_score}")
    print(f"Match: {response.result.is_match}")
    print(f"Reasons: {response.result.match_reasons}")
```

---

## Project Structure

```
matchmaking/
├── __init__.py                    # Package init, version
├── config/
│   ├── __init__.py
│   └── matchmaking_config.py      # Centralized configuration
├── schemas/
│   ├── __init__.py                # Pydantic input/output contracts
│   ├── examples.py                # Swagger example payloads
├── models/
│   ├── __init__.py                # AiMatchMakingModel
├── exceptions/
│   ├── __init__.py                # Custom exception hierarchy
├── processing/
│   ├── __init__.py
│   ├── normalizer.py              # Input normalization
│   ├── validator.py               # Input validation
│   ├── preference_processor.py    # Preference classification
│   ├── scoring_engine.py          # Criterion-level scoring
│   ├── compatibility_engine.py    # Overall compatibility calculation
│   ├── ranking_engine.py          # Multi-candidate ranking
│   └── mutual_engine.py           # Two-way (mutual) matchmaking
├── ai/
│   ├── __init__.py
│   ├── ai_provider.py             # LLM communication
│   ├── prompt_builder.py          # AI prompt construction
│   └── ai_matchmaking_service.py  # AI enhancement service
├── services/
│   ├── __init__.py
│   └── matchmaking_service.py     # Main orchestration service
├── tests/
│   ├── fixtures/
│   │   └── test_data.py           # Shared test fixtures
│   ├── unit/
│   │   ├── test_config.py
│   │   ├── test_normalizer.py
│   │   ├── test_validator.py
│   │   ├── test_schemas.py
│   │   ├── test_scoring_engine.py
│   │   ├── test_preference_processor.py
│   │   └── test_compatibility_engine.py
│   └── integration/
│       └── test_matchmaking_pipeline.py
├── DOCUMENTATION.md               # This file
├── requirements.txt               # Python dependencies
app.py                             # FastAPI application
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MODEL_VERSION` | `1.0.0` | Model version string |
| `MATCH_THRESHOLD` | `70` | Minimum score for `is_match` |
| `AI_ENABLED` | `true` | Enable/disable AI enhancement |
| `AI_PROVIDER` | `openai` | AI provider name |
| `AI_MODEL` | `gpt-4o` | AI model to use |
| `AI_TEMPERATURE` | `0.1` | AI temperature (lower = more deterministic) |
| `AI_TIMEOUT` | `30` | AI request timeout (seconds) |
| `AI_MAX_RETRIES` | `2` | Max AI retries |
| `MAX_CANDIDATES_PER_REQUEST` | `100` | Max candidates per batch |
| `SCORING_WEIGHT_*` | varies | Per-criterion scoring weights |

---

## Running

```bash
# Install dependencies
pip install -r requirements.txt

# Start the server
uvicorn app:app --host 0.0.0.0 --port 8000 --reload

# Run tests
cd matchmaking && python -m pytest tests/ -v

# Health check
curl http://localhost:8000/health

# Get config
curl http://localhost:8000/matchmaking/config

# Swagger UI - the mutual matchmaking endpoint is pre-filled with a
# runnable example; just open it and press Execute
open http://localhost:8000/docs
```
