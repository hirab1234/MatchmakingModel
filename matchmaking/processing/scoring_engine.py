"""
Scoring Engine

Implements criterion-level scoring for matchmaking.

Each criterion (age, location, education, ...) is evaluated independently,
producing a score between 0-100. Scores are then weighted and combined
into an overall compatibility score.

Score calculation:
    Final = Sum(criterion_score * criterion_weight) / Sum(criterion_weights)

...over the criteria that are APPLICABLE. A criterion is applicable only when
the user actually expressed that preference. An unspecified preference is
excluded from the average entirely, so a sparsely filled preference form no
longer drags every result towards 50%.

Criteria implemented (section 17 of the product document):
    age, height, location (city + country), marital status, mother tongue,
    religion, sect, religious practice, education (incl. minimum education),
    education field, profession, employment status, income, family structure,
    living arrangement, family involvement, smoking, drinking, diet, exercise,
    social lifestyle, free-form lifestyle, personality traits, interests,
    marriage timeline, children preference, relocation, career expectations.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from matchmaking.config import MatchmakingConfig, get_config
from matchmaking.schemas import (
    CareerExpectation,
    ChildrenPreference,
    CriterionMatch,
    EducationLevel,
    ExerciseFrequency,
    FamilyInvolvement,
    IncomeRange,
    LivingArrangement,
    MarriageTimeline,
    MatchStatus,
    PartnerPreferences,
    ReligiousPractice,
    SocialLifestyle,
    UserProfile,
)


# ---------------------------------------------------------------------------
# Ordinal scales: values that sit on a spectrum, so "close" deserves credit
# ---------------------------------------------------------------------------

EDUCATION_ORDER: Dict[EducationLevel, int] = {
    EducationLevel.HIGH_SCHOOL: 1,
    EducationLevel.DIPLOMA: 2,
    EducationLevel.BACHELORS: 3,
    EducationLevel.MASTERS: 4,
    EducationLevel.DOCTORATE: 5,
    EducationLevel.PROFESSIONAL: 5,
    EducationLevel.OTHER: 3,
    EducationLevel.UNKNOWN: 0,
}

RELIGIOUS_PRACTICE_ORDER: Dict[str, int] = {
    ReligiousPractice.NOT_PRACTICING.value: 1,
    ReligiousPractice.OCCASIONALLY_PRACTICING.value: 2,
    ReligiousPractice.MODERATELY_PRACTICING.value: 3,
    ReligiousPractice.PRACTICING.value: 4,
    ReligiousPractice.VERY_PRACTICING.value: 5,
}

EXERCISE_ORDER: Dict[str, int] = {
    ExerciseFrequency.NEVER.value: 1,
    ExerciseFrequency.RARELY.value: 2,
    ExerciseFrequency.OCCASIONAL.value: 3,
    ExerciseFrequency.REGULAR.value: 4,
    ExerciseFrequency.DAILY.value: 5,
}

SOCIAL_LIFESTYLE_ORDER: Dict[str, int] = {
    SocialLifestyle.HOMEBODY.value: 1,
    SocialLifestyle.RESERVED.value: 2,
    SocialLifestyle.BALANCED.value: 3,
    SocialLifestyle.SOCIAL.value: 4,
    SocialLifestyle.VERY_SOCIAL.value: 5,
}

FAMILY_INVOLVEMENT_ORDER: Dict[str, int] = {
    FamilyInvolvement.MINIMAL.value: 1,
    FamilyInvolvement.LOW.value: 2,
    FamilyInvolvement.MODERATE.value: 3,
    FamilyInvolvement.HIGH.value: 4,
}

MARRIAGE_TIMELINE_ORDER: Dict[str, int] = {
    MarriageTimeline.IMMEDIATELY.value: 1,
    MarriageTimeline.WITHIN_6_MONTHS.value: 2,
    MarriageTimeline.WITHIN_1_YEAR.value: 3,
    MarriageTimeline.WITHIN_2_YEARS.value: 4,
    MarriageTimeline.NO_RUSH.value: 5,
}

# Values that partially satisfy any preference because the person is open
FLEXIBLE_VALUES: Dict[str, Dict[str, float]] = {
    "living_arrangement": {LivingArrangement.FLEXIBLE.value: 70.0},
    "children_preference": {
        ChildrenPreference.OPEN_TO_CHILDREN.value: 70.0,
        ChildrenPreference.UNDECIDED.value: 45.0,
    },
    "career_expectation": {
        CareerExpectation.FLEXIBLE.value: 70.0,
        CareerExpectation.UNDECIDED.value: 45.0,
    },
    "marriage_timeline": {MarriageTimeline.UNDECIDED.value: 40.0},
}

# Pairs that are actively incompatible, not merely different
HARD_CONFLICTS: Dict[str, List[Tuple[str, str]]] = {
    "children_preference": [
        (
            ChildrenPreference.DONT_WANT_CHILDREN.value,
            ChildrenPreference.WANT_CHILDREN.value,
        ),
        (
            ChildrenPreference.DONT_WANT_CHILDREN.value,
            ChildrenPreference.HAVE_AND_WANT_MORE.value,
        ),
        (
            ChildrenPreference.HAVE_AND_NO_MORE.value,
            ChildrenPreference.WANT_CHILDREN.value,
        ),
    ],
    "career_expectation": [
        (
            CareerExpectation.STOP_AFTER_MARRIAGE.value,
            CareerExpectation.CONTINUE_CAREER.value,
        ),
    ],
}


def _val(v: Any) -> Optional[str]:
    """Enum or string -> lowercase string."""
    if v is None:
        return None
    if hasattr(v, "value"):
        return str(v.value).lower()
    return str(v).strip().lower()


def _vals(items: Optional[Iterable[Any]]) -> List[str]:
    if not items:
        return []
    out = []
    for i in items:
        s = _val(i)
        if s:
            out.append(s)
    return out


def _parse_money(text: Optional[str]) -> Tuple[Optional[float], Optional[float]]:
    """Extract a (min, max) pair from a free-text income band.

    Handles '150000-300000', '150,000 to 300,000 PKR', '200000+', '180000'.
    """
    if not text:
        return None, None
    numbers = [
        float(n.replace(",", ""))
        for n in re.findall(r"\d[\d,]*(?:\.\d+)?", str(text))
    ]
    if not numbers:
        return None, None
    if len(numbers) == 1:
        if "+" in str(text) or "above" in str(text).lower():
            return numbers[0], None
        return numbers[0], numbers[0]
    return min(numbers), max(numbers)


class ScoringEngine:
    """Calculates criterion-level and overall compatibility scores."""

    def __init__(self, config: Optional[MatchmakingConfig] = None):
        self.config = config or get_config()
        self.weights = self.config.weights.to_dict()

    # ------------------------------------------------------------------
    # Orchestration
    # ------------------------------------------------------------------

    def score_all_criteria(
        self,
        user: UserProfile,
        candidate: UserProfile,
        prefs: PartnerPreferences,
    ) -> Tuple[List[CriterionMatch], float, Dict[str, float]]:
        """Score the candidate against all preference criteria.

        Returns:
            Tuple of (criterion_matches, overall_score, criterion_scores_dict)
        """
        criteria: List[CriterionMatch] = [
            # Basic
            self._score_age(candidate, prefs),
            self._score_height(candidate, prefs),
            self._score_location(candidate, prefs),
            self._score_marital_status(candidate, prefs),
            self._score_mother_tongue(candidate, prefs),
            # Religion
            self._score_religion(candidate, prefs),
            self._score_sect(candidate, prefs),
            self._score_religious_practice(candidate, prefs),
            # Education / career
            self._score_education(candidate, prefs),
            self._score_education_field(candidate, prefs),
            self._score_profession(candidate, prefs),
            self._score_employment_status(candidate, prefs),
            self._score_income(candidate, prefs),
            # Family
            self._score_family_structure(candidate, prefs),
            self._score_living_arrangement(candidate, prefs),
            self._score_family_involvement(candidate, prefs),
            # Lifestyle
            self._score_smoking(candidate, prefs),
            self._score_drinking(candidate, prefs),
            self._score_diet(candidate, prefs),
            self._score_exercise(candidate, prefs),
            self._score_social_lifestyle(candidate, prefs),
            self._score_lifestyle(candidate, prefs),
            # Personality / interests
            self._score_personality(candidate, prefs),
            self._score_interests(candidate, prefs),
            # Marriage expectations
            self._score_marriage_timeline(candidate, prefs),
            self._score_children_preference(candidate, prefs),
            self._score_relocation(candidate, prefs),
            self._score_career_expectation(candidate, prefs),
        ]

        criterion_scores: Dict[str, float] = {c.criterion: c.score for c in criteria}
        overall_score = self._calculate_weighted_score(criteria)

        return criteria, overall_score, criterion_scores

    def _calculate_weighted_score(self, criteria: List[CriterionMatch]) -> float:
        """Weighted average over the APPLICABLE criteria only.

        Formula: Sum(score * weight) / Sum(weights), skipping criteria the
        user never expressed a preference for.
        """
        total_weighted = 0.0
        total_weight = 0.0

        for c in criteria:
            if not c.applicable:
                continue
            w = self.weights.get(c.criterion, 0.0)
            if w > 0:
                total_weighted += c.score * w
                total_weight += w

        if total_weight == 0:
            return self.config.missing_data_score

        return round(total_weighted / total_weight, 2)

    # ------------------------------------------------------------------
    # Shared builders
    # ------------------------------------------------------------------

    def _not_applicable(
        self, criterion: str, candidate_value: Any = None
    ) -> CriterionMatch:
        """The user did not express this preference - exclude it from scoring."""
        weight = self.weights.get(criterion, 0.0)
        score = self.config.missing_data_score
        return CriterionMatch(
            criterion=criterion,
            score=score,
            weight=weight,
            weighted_score=round(score * weight, 2),
            status=MatchStatus.UNKNOWN,
            reason=f"No {criterion.replace('_', ' ')} preference specified",
            applicable=False,
            candidate_value=candidate_value,
            preference_value=None,
        )

    def _missing_candidate_data(
        self, criterion: str, preference_value: Any
    ) -> CriterionMatch:
        """Preference exists but the candidate has not filled this field in."""
        weight = self.weights.get(criterion, 0.0)
        score = self.config.missing_data_score
        return CriterionMatch(
            criterion=criterion,
            score=score,
            weight=weight,
            weighted_score=round(score * weight, 2),
            status=MatchStatus.UNKNOWN,
            reason=f"Candidate {criterion.replace('_', ' ')} not provided",
            applicable=True,
            candidate_value=None,
            preference_value=preference_value,
        )

    def _build(
        self,
        criterion: str,
        score: float,
        status: MatchStatus,
        reason: str,
        candidate_value: Any = None,
        preference_value: Any = None,
        is_hard_constraint: bool = False,
    ) -> CriterionMatch:
        weight = self.weights.get(criterion, 0.0)
        score = round(max(0.0, min(100.0, score)), 1)
        return CriterionMatch(
            criterion=criterion,
            score=score,
            weight=weight,
            weighted_score=round(score * weight, 2),
            status=status,
            reason=reason,
            applicable=True,
            candidate_value=candidate_value,
            preference_value=preference_value,
            is_hard_constraint=is_hard_constraint,
        )

    @staticmethod
    def _status_for(score: float) -> MatchStatus:
        if score >= 70:
            return MatchStatus.MATCH
        if score >= 40:
            return MatchStatus.PARTIAL_MATCH
        return MatchStatus.NO_MATCH

    def _score_ordinal(
        self,
        criterion: str,
        candidate_value: Any,
        pref_values: Optional[Sequence[Any]],
        order: Dict[str, int],
        label: str,
        step_penalty: float = 25.0,
    ) -> CriterionMatch:
        """Score a value that lies on a spectrum.

        Exact membership scores 100; anything else loses `step_penalty`
        points per step away from the nearest acceptable value.
        """
        prefs_list = _vals(pref_values)
        if not prefs_list:
            return self._not_applicable(criterion, _val(candidate_value))

        cand = _val(candidate_value)
        if cand is None or cand == "unknown":
            return self._missing_candidate_data(criterion, prefs_list)

        if cand in prefs_list:
            return self._build(
                criterion, 100.0, MatchStatus.MATCH,
                f"{label} matches: {cand}", cand, prefs_list,
            )

        # Flexible / open values earn partial credit
        flexible = FLEXIBLE_VALUES.get(criterion, {})
        if cand in flexible:
            score = flexible[cand]
            return self._build(
                criterion, score, self._status_for(score),
                f"{label} is open-ended ({cand}), partially compatible with {prefs_list}",
                cand, prefs_list,
            )

        cand_rank = order.get(cand)
        pref_ranks = [order[p] for p in prefs_list if p in order]
        if cand_rank is None or not pref_ranks:
            return self._build(
                criterion, 25.0, MatchStatus.NO_MATCH,
                f"{label} differs: candidate={cand}, preferred={prefs_list}",
                cand, prefs_list,
            )

        distance = min(abs(cand_rank - r) for r in pref_ranks)
        score = max(0.0, 100.0 - distance * step_penalty)
        return self._build(
            criterion, score, self._status_for(score),
            f"{label} is {distance} step(s) from preference: "
            f"candidate={cand}, preferred={prefs_list}",
            cand, prefs_list,
        )

    def _score_categorical(
        self,
        criterion: str,
        candidate_value: Any,
        pref_values: Optional[Sequence[Any]],
        label: str,
        mismatch_score: float = 25.0,
    ) -> CriterionMatch:
        """Score a value from an unordered set of options."""
        prefs_list = _vals(pref_values)
        if not prefs_list:
            return self._not_applicable(criterion, _val(candidate_value))

        cand = _val(candidate_value)
        if cand is None or cand == "unknown":
            return self._missing_candidate_data(criterion, prefs_list)

        if cand in prefs_list:
            return self._build(
                criterion, 100.0, MatchStatus.MATCH,
                f"{label} matches: {cand}", cand, prefs_list,
            )

        # Actively incompatible pairs score zero
        for a, b in HARD_CONFLICTS.get(criterion, []):
            if (cand == a and b in prefs_list) or (cand == b and a in prefs_list):
                return self._build(
                    criterion, 0.0, MatchStatus.NO_MATCH,
                    f"{label} conflicts: candidate={cand}, preferred={prefs_list}",
                    cand, prefs_list,
                )

        flexible = FLEXIBLE_VALUES.get(criterion, {})
        if cand in flexible:
            score = flexible[cand]
            return self._build(
                criterion, score, self._status_for(score),
                f"{label} is open-ended ({cand}), partially compatible with {prefs_list}",
                cand, prefs_list,
            )

        return self._build(
            criterion, mismatch_score, self._status_for(mismatch_score),
            f"{label} differs: candidate={cand}, preferred={prefs_list}",
            cand, prefs_list,
        )

    @staticmethod
    def _jaccard(pref: Sequence[str], cand: Sequence[str]) -> Tuple[float, List[str], List[str]]:
        pref_set = {p.lower().strip() for p in pref}
        cand_set = {c.lower().strip() for c in cand}
        union = pref_set | cand_set
        if not union:
            return 50.0, [], []
        intersection = pref_set & cand_set
        score = round(len(intersection) / len(union) * 100, 1)
        return score, sorted(intersection), sorted(pref_set - cand_set)

    # ------------------------------------------------------------------
    # Basic criteria
    # ------------------------------------------------------------------

    def _score_age(
        self, candidate: UserProfile, prefs: PartnerPreferences
    ) -> CriterionMatch:
        """Score age compatibility (document field 1)."""
        age = candidate.age

        if prefs.age_range is None:
            return self._not_applicable("age", age)

        pref_label = f"{prefs.age_range.min}-{prefs.age_range.max}"
        if age is None:
            return self._missing_candidate_data("age", pref_label)

        min_age = prefs.age_range.min or 18
        max_age = prefs.age_range.max or 100
        pref_label = f"{min_age}-{max_age}"

        if min_age <= age <= max_age:
            # Within range: highest score near the centre of the range
            range_center = (min_age + max_age) / 2
            range_half = (max_age - min_age) / 2 or 1
            distance = abs(age - range_center)
            score = max(0.0, 100.0 - (distance / range_half) * 20)
            return self._build(
                "age", score, MatchStatus.MATCH,
                f"Age {age} is within preferred range {pref_label}",
                age, pref_label,
            )

        distance = (min_age - age) if age < min_age else (age - max_age)
        score = max(0.0, 100.0 - distance * 5)
        return self._build(
            "age", score, MatchStatus.NO_MATCH,
            f"Age {age} is outside preferred range {pref_label}",
            age, pref_label,
        )

    def _score_height(
        self, candidate: UserProfile, prefs: PartnerPreferences
    ) -> CriterionMatch:
        """Score height compatibility (document field 2)."""
        height = candidate.height_cm

        if prefs.height_range is None:
            return self._not_applicable("height", height)

        min_h = prefs.height_range.min_cm or 100
        max_h = prefs.height_range.max_cm or 250
        pref_label = f"{min_h}-{max_h}"

        if height is None:
            return self._missing_candidate_data("height", pref_label)

        if min_h <= height <= max_h:
            return self._build(
                "height", 100.0, MatchStatus.MATCH,
                f"Height {height}cm is within preferred range {pref_label}cm",
                height, pref_label,
            )

        distance = abs(height - (min_h if height < min_h else max_h))
        score = max(0.0, 100.0 - distance * 2)
        return self._build(
            "height", score, self._status_for(score),
            f"Height {height}cm is outside preferred range {pref_label}cm",
            height, pref_label,
        )

    def _score_location(
        self, candidate: UserProfile, prefs: PartnerPreferences
    ) -> CriterionMatch:
        """Score city + country compatibility (document fields 3 and 4)."""
        pref_label = {"cities": prefs.location, "countries": prefs.country}

        if not prefs.location and not prefs.country:
            return self._not_applicable("location", None)

        if candidate.location is None:
            return self._missing_candidate_data("location", pref_label)

        city_match = bool(
            prefs.location
            and candidate.location.city
            and any(
                candidate.location.city.lower() == loc.lower()
                for loc in prefs.location
            )
        )
        country_match = bool(
            prefs.country
            and candidate.location.country
            and any(
                candidate.location.country.lower() == c.lower()
                for c in prefs.country
            )
        )

        if prefs.location and prefs.country:
            if city_match and country_match:
                score, reason = 100.0, "Both city and country match preferences"
            elif city_match:
                score, reason = 85.0, "City matches, country does not"
            elif country_match:
                score, reason = 60.0, "Country matches but city does not"
            else:
                score, reason = 20.0, "Neither city nor country matches preferences"
        elif prefs.location:
            score, reason = (
                (100.0, "City matches preference")
                if city_match
                else (20.0, f"City does not match preference {prefs.location}")
            )
        else:
            score, reason = (
                (100.0, "Country matches preference")
                if country_match
                else (20.0, f"Country does not match preference {prefs.country}")
            )

        return self._build(
            "location", score, self._status_for(score), reason,
            candidate.location.model_dump(), pref_label,
        )

    def _score_marital_status(
        self, candidate: UserProfile, prefs: PartnerPreferences
    ) -> CriterionMatch:
        """Score marital status compatibility (document field 5)."""
        if not prefs.marital_status:
            return self._not_applicable("marital_status", _val(candidate.marital_status))

        pref_list = [m.value for m in prefs.marital_status]

        if candidate.marital_status is None:
            match = self._missing_candidate_data("marital_status", pref_list)
            return match.model_copy(update={"is_hard_constraint": True})

        if candidate.marital_status.value in pref_list:
            return self._build(
                "marital_status", 100.0, MatchStatus.MATCH,
                f"Marital status matches: {candidate.marital_status.value}",
                candidate.marital_status.value, pref_list,
            )

        return self._build(
            "marital_status", 0.0, MatchStatus.NO_MATCH,
            f"Marital status mismatch: {candidate.marital_status.value} "
            f"vs {pref_list}",
            candidate.marital_status.value, pref_list,
            is_hard_constraint=True,
        )

    def _score_mother_tongue(
        self, candidate: UserProfile, prefs: PartnerPreferences
    ) -> CriterionMatch:
        """Score mother tongue compatibility."""
        if not prefs.mother_tongue:
            return self._not_applicable("mother_tongue", candidate.mother_tongue)

        if candidate.mother_tongue is None:
            return self._missing_candidate_data("mother_tongue", prefs.mother_tongue)

        if any(
            candidate.mother_tongue.lower() == mt.lower()
            for mt in prefs.mother_tongue
        ):
            return self._build(
                "mother_tongue", 100.0, MatchStatus.MATCH,
                f"Mother tongue matches: {candidate.mother_tongue}",
                candidate.mother_tongue, prefs.mother_tongue,
            )

        return self._build(
            "mother_tongue", 45.0, MatchStatus.PARTIAL_MATCH,
            f"Mother tongue differs: {candidate.mother_tongue}",
            candidate.mother_tongue, prefs.mother_tongue,
        )

    # ------------------------------------------------------------------
    # Religion
    # ------------------------------------------------------------------

    def _score_religion(
        self, candidate: UserProfile, prefs: PartnerPreferences
    ) -> CriterionMatch:
        """Score religion compatibility (document field 6)."""
        if not prefs.religion:
            return self._not_applicable("religion", candidate.religion)

        if candidate.religion is None:
            return self._build(
                "religion", 30.0, MatchStatus.NO_MATCH,
                "Candidate religion not provided but is required",
                None, prefs.religion, is_hard_constraint=True,
            )

        if any(candidate.religion.lower() == r.lower() for r in prefs.religion):
            return self._build(
                "religion", 100.0, MatchStatus.MATCH,
                f"Religion matches: {candidate.religion}",
                candidate.religion, prefs.religion,
            )

        return self._build(
            "religion", 0.0, MatchStatus.NO_MATCH,
            f"Religion mismatch: candidate={candidate.religion}, "
            f"preferred={prefs.religion}",
            candidate.religion, prefs.religion, is_hard_constraint=True,
        )

    def _score_sect(
        self, candidate: UserProfile, prefs: PartnerPreferences
    ) -> CriterionMatch:
        """Score sect compatibility (document field 7)."""
        if not prefs.sect:
            return self._not_applicable("sect", candidate.sect)

        if candidate.sect is None:
            return self._missing_candidate_data("sect", prefs.sect)

        if any(candidate.sect.lower() == s.lower() for s in prefs.sect):
            return self._build(
                "sect", 100.0, MatchStatus.MATCH,
                f"Sect matches: {candidate.sect}",
                candidate.sect, prefs.sect,
            )

        return self._build(
            "sect", 20.0, MatchStatus.NO_MATCH,
            f"Sect differs: candidate={candidate.sect}, preferred={prefs.sect}",
            candidate.sect, prefs.sect,
        )

    def _score_religious_practice(
        self, candidate: UserProfile, prefs: PartnerPreferences
    ) -> CriterionMatch:
        """Score religious practice level (document field 8)."""
        return self._score_ordinal(
            "religious_practice",
            candidate.religious_practice,
            prefs.religious_practice,
            RELIGIOUS_PRACTICE_ORDER,
            "Religious practice",
        )

    # ------------------------------------------------------------------
    # Education / career
    # ------------------------------------------------------------------

    def _score_education(
        self, candidate: UserProfile, prefs: PartnerPreferences
    ) -> CriterionMatch:
        """Score education, honouring both an allow-list and a minimum level.

        Document fields 9 (minimum education) and the education allow-list.
        When both are given the candidate gets the better of the two scores.
        """
        has_list = bool(prefs.education)
        has_min = prefs.min_education is not None

        if not has_list and not has_min:
            return self._not_applicable("education", _val(candidate.education))

        pref_label: Dict[str, Any] = {}
        if has_list:
            pref_label["allowed"] = [e.value for e in prefs.education]
        if has_min:
            pref_label["minimum"] = prefs.min_education.value

        if candidate.education is None:
            return self._missing_candidate_data("education", pref_label)

        candidate_level = EDUCATION_ORDER.get(candidate.education, 0)
        best_score = 0.0
        best_reason = ""

        if has_min:
            min_level = EDUCATION_ORDER.get(prefs.min_education, 0)
            if candidate_level >= min_level:
                best_score = 100.0
                best_reason = (
                    f"Education {candidate.education.value} meets the minimum "
                    f"of {prefs.min_education.value}"
                )
            else:
                gap = min_level - candidate_level
                best_score = max(15.0, 80.0 - gap * 25)
                best_reason = (
                    f"Education {candidate.education.value} is below the minimum "
                    f"of {prefs.min_education.value}"
                )

        if has_list:
            allowed = [e.value for e in prefs.education]
            preferred_levels = [EDUCATION_ORDER.get(e, 0) for e in prefs.education]
            if candidate.education.value in allowed:
                list_score = 100.0
                list_reason = f"Education level matches: {candidate.education.value}"
            elif preferred_levels and candidate_level > max(preferred_levels):
                list_score = 85.0
                list_reason = f"Candidate over-qualified: {candidate.education.value}"
            elif preferred_levels:
                gap = max(preferred_levels) - candidate_level
                list_score = max(20.0, 80.0 - gap * 20)
                list_reason = f"Candidate under-qualified: {candidate.education.value}"
            else:
                list_score = 50.0
                list_reason = "Education level partially compatible"

            if list_score >= best_score:
                best_score, best_reason = list_score, list_reason

        return self._build(
            "education", best_score, self._status_for(best_score), best_reason,
            candidate.education.value, pref_label,
        )

    def _score_education_field(
        self, candidate: UserProfile, prefs: PartnerPreferences
    ) -> CriterionMatch:
        """Score field of study (document field 10: preferred field)."""
        if not prefs.preferred_field:
            return self._not_applicable("education_field", candidate.education_field)

        if not candidate.education_field:
            return self._missing_candidate_data(
                "education_field", prefs.preferred_field
            )

        cand = candidate.education_field.lower().strip()
        wanted = [f.lower().strip() for f in prefs.preferred_field]

        if cand in wanted:
            return self._build(
                "education_field", 100.0, MatchStatus.MATCH,
                f"Field of study matches: {candidate.education_field}",
                candidate.education_field, prefs.preferred_field,
            )

        if any(cand in w or w in cand for w in wanted):
            return self._build(
                "education_field", 75.0, MatchStatus.PARTIAL_MATCH,
                f"Field of study is related: {candidate.education_field}",
                candidate.education_field, prefs.preferred_field,
            )

        return self._build(
            "education_field", 25.0, MatchStatus.NO_MATCH,
            f"Field of study differs: {candidate.education_field}",
            candidate.education_field, prefs.preferred_field,
        )

    def _score_profession(
        self, candidate: UserProfile, prefs: PartnerPreferences
    ) -> CriterionMatch:
        """Score profession compatibility (document field 11)."""
        if not prefs.profession and not prefs.profession_category:
            return self._not_applicable("profession", candidate.profession)

        pref_label = {
            "professions": prefs.profession,
            "categories": prefs.profession_category,
        }

        if candidate.profession is None and candidate.profession_category is None:
            return self._missing_candidate_data("profession", pref_label)

        if prefs.profession and candidate.profession:
            if any(
                candidate.profession.lower() == p.lower() for p in prefs.profession
            ):
                return self._build(
                    "profession", 100.0, MatchStatus.MATCH,
                    f"Profession matches: {candidate.profession}",
                    candidate.profession, pref_label,
                )

        if prefs.profession_category and candidate.profession_category:
            if any(
                candidate.profession_category.lower() == c.lower()
                for c in prefs.profession_category
            ):
                return self._build(
                    "profession", 80.0, MatchStatus.MATCH,
                    f"Profession category matches: {candidate.profession_category}",
                    candidate.profession_category, pref_label,
                )

        return self._build(
            "profession", 35.0, MatchStatus.NO_MATCH,
            f"Profession does not match preference: {candidate.profession}",
            candidate.profession, pref_label,
        )

    def _score_employment_status(
        self, candidate: UserProfile, prefs: PartnerPreferences
    ) -> CriterionMatch:
        """Score employment status (document field 12)."""
        return self._score_categorical(
            "employment_status",
            candidate.employment_status,
            prefs.employment_status,
            "Employment status",
            mismatch_score=20.0,
        )

    def _score_income(
        self, candidate: UserProfile, prefs: PartnerPreferences
    ) -> CriterionMatch:
        """Score income against the preferred band (document field 13)."""
        pref_min = pref_max = None
        pref_label: Any = None

        if isinstance(prefs.income_range, IncomeRange):
            pref_min, pref_max = prefs.income_range.min, prefs.income_range.max
            pref_label = prefs.income_range.model_dump(exclude_none=True)
        elif isinstance(prefs.income_range, str):
            pref_min, pref_max = _parse_money(prefs.income_range)
            pref_label = prefs.income_range

        if pref_min is None and pref_max is None:
            return self._not_applicable("income", candidate.monthly_income)

        income = candidate.monthly_income
        if income is None:
            parsed_min, parsed_max = _parse_money(candidate.income_range)
            if parsed_min is not None and parsed_max is not None:
                income = (parsed_min + parsed_max) / 2
            else:
                income = parsed_min

        if income is None:
            return self._missing_candidate_data("income", pref_label)

        if pref_min is not None and income < pref_min:
            ratio = income / pref_min if pref_min else 0.0
            score = max(0.0, ratio * 100.0)
            return self._build(
                "income", score, self._status_for(score),
                f"Income {income:,.0f} is below the preferred minimum {pref_min:,.0f}",
                income, pref_label,
            )

        if pref_max is not None and income > pref_max:
            return self._build(
                "income", 90.0, MatchStatus.MATCH,
                f"Income {income:,.0f} is above the preferred band (acceptable)",
                income, pref_label,
            )

        return self._build(
            "income", 100.0, MatchStatus.MATCH,
            f"Income {income:,.0f} is within the preferred range",
            income, pref_label,
        )

    # ------------------------------------------------------------------
    # Family
    # ------------------------------------------------------------------

    def _score_family_structure(
        self, candidate: UserProfile, prefs: PartnerPreferences
    ) -> CriterionMatch:
        """Score family structure (document field 14)."""
        return self._score_categorical(
            "family_structure",
            candidate.family_structure,
            prefs.family_structure,
            "Family structure",
            mismatch_score=35.0,
        )

    def _score_living_arrangement(
        self, candidate: UserProfile, prefs: PartnerPreferences
    ) -> CriterionMatch:
        """Score living arrangement (document field 15)."""
        return self._score_categorical(
            "living_arrangement",
            candidate.living_arrangement,
            prefs.living_arrangement,
            "Living arrangement",
            mismatch_score=25.0,
        )

    def _score_family_involvement(
        self, candidate: UserProfile, prefs: PartnerPreferences
    ) -> CriterionMatch:
        """Score family involvement (document field 16)."""
        return self._score_ordinal(
            "family_involvement",
            candidate.family_involvement,
            prefs.family_involvement,
            FAMILY_INVOLVEMENT_ORDER,
            "Family involvement",
            step_penalty=30.0,
        )

    # ------------------------------------------------------------------
    # Lifestyle
    # ------------------------------------------------------------------

    def _score_smoking(
        self, candidate: UserProfile, prefs: PartnerPreferences
    ) -> CriterionMatch:
        """Score smoking compatibility (document field 17)."""
        if prefs.smoking is None:
            return self._not_applicable("smoking", candidate.smoking)

        if candidate.smoking is None:
            return self._missing_candidate_data("smoking", prefs.smoking)

        if prefs.smoking is False and candidate.smoking is True:
            return self._build(
                "smoking", 0.0, MatchStatus.NO_MATCH,
                "Candidate smokes but non-smoker preferred",
                candidate.smoking, prefs.smoking, is_hard_constraint=True,
            )

        if prefs.smoking == candidate.smoking:
            return self._build(
                "smoking", 100.0, MatchStatus.MATCH,
                "Smoking preference matches",
                candidate.smoking, prefs.smoking,
            )

        return self._build(
            "smoking", 60.0, MatchStatus.PARTIAL_MATCH,
            "Smoking preference differs but not a deal breaker",
            candidate.smoking, prefs.smoking,
        )

    def _score_drinking(
        self, candidate: UserProfile, prefs: PartnerPreferences
    ) -> CriterionMatch:
        """Score drinking compatibility."""
        if prefs.drinking is None:
            return self._not_applicable("drinking", candidate.drinking)

        if candidate.drinking is None:
            return self._missing_candidate_data("drinking", prefs.drinking)

        if prefs.drinking is False and candidate.drinking is True:
            return self._build(
                "drinking", 0.0, MatchStatus.NO_MATCH,
                "Candidate drinks but non-drinker preferred",
                candidate.drinking, prefs.drinking, is_hard_constraint=True,
            )

        if prefs.drinking == candidate.drinking:
            return self._build(
                "drinking", 100.0, MatchStatus.MATCH,
                "Drinking preference matches",
                candidate.drinking, prefs.drinking,
            )

        return self._build(
            "drinking", 60.0, MatchStatus.PARTIAL_MATCH,
            "Drinking preference differs but not a deal breaker",
            candidate.drinking, prefs.drinking,
        )

    def _score_diet(
        self, candidate: UserProfile, prefs: PartnerPreferences
    ) -> CriterionMatch:
        """Score diet compatibility (document field 18)."""
        if not prefs.diet:
            return self._not_applicable("diet", candidate.diet)

        if not candidate.diet:
            return self._missing_candidate_data("diet", prefs.diet)

        cand = candidate.diet.lower().strip()
        wanted = [d.lower().strip() for d in prefs.diet]

        if cand in wanted:
            return self._build(
                "diet", 100.0, MatchStatus.MATCH,
                f"Diet matches: {candidate.diet}",
                candidate.diet, prefs.diet,
            )

        if any(cand in w or w in cand for w in wanted):
            return self._build(
                "diet", 75.0, MatchStatus.MATCH,
                f"Diet is compatible: {candidate.diet}",
                candidate.diet, prefs.diet,
            )

        return self._build(
            "diet", 25.0, MatchStatus.NO_MATCH,
            f"Diet differs: candidate={candidate.diet}, preferred={prefs.diet}",
            candidate.diet, prefs.diet,
        )

    def _score_exercise(
        self, candidate: UserProfile, prefs: PartnerPreferences
    ) -> CriterionMatch:
        """Score exercise habits (document field 19)."""
        return self._score_ordinal(
            "exercise",
            candidate.exercise,
            prefs.exercise,
            EXERCISE_ORDER,
            "Exercise frequency",
            step_penalty=20.0,
        )

    def _score_social_lifestyle(
        self, candidate: UserProfile, prefs: PartnerPreferences
    ) -> CriterionMatch:
        """Score social lifestyle (document field 20)."""
        return self._score_ordinal(
            "social_lifestyle",
            candidate.social_lifestyle,
            prefs.social_lifestyle,
            SOCIAL_LIFESTYLE_ORDER,
            "Social lifestyle",
            step_penalty=22.0,
        )

    def _score_lifestyle(
        self, candidate: UserProfile, prefs: PartnerPreferences
    ) -> CriterionMatch:
        """Score the free-form lifestyle dictionary."""
        if not prefs.lifestyle:
            return self._not_applicable("lifestyle", candidate.lifestyle or None)

        if not candidate.lifestyle:
            return self._missing_candidate_data("lifestyle", prefs.lifestyle)

        matches = 0
        total = 0
        for key, pref_val in prefs.lifestyle.items():
            cand_val = candidate.lifestyle.get(key)
            if cand_val is not None:
                total += 1
                if str(cand_val).lower() == str(pref_val).lower():
                    matches += 1

        if total == 0:
            return self._missing_candidate_data("lifestyle", prefs.lifestyle)

        score = round((matches / total) * 100, 1)
        return self._build(
            "lifestyle", score, self._status_for(score),
            f"Lifestyle attributes aligned ({matches}/{total})",
            candidate.lifestyle, prefs.lifestyle,
        )

    # ------------------------------------------------------------------
    # Personality / interests
    # ------------------------------------------------------------------

    def _score_personality(
        self, candidate: UserProfile, prefs: PartnerPreferences
    ) -> CriterionMatch:
        """Score personality trait overlap (document field 21)."""
        if not prefs.personality_traits:
            return self._not_applicable(
                "personality", candidate.personality_traits or None
            )

        if not candidate.personality_traits:
            return self._missing_candidate_data(
                "personality", prefs.personality_traits
            )

        score, shared, missing = self._jaccard(
            prefs.personality_traits, candidate.personality_traits
        )

        if score >= 70:
            reason = f"Strong personality alignment: {shared[:3]}"
        elif score >= 30:
            reason = f"Some personality alignment, missing: {missing[:3]}"
        else:
            reason = "Low personality alignment"

        return self._build(
            "personality", score, self._status_for_overlap(score), reason,
            candidate.personality_traits, prefs.personality_traits,
        )

    def _score_interests(
        self, candidate: UserProfile, prefs: PartnerPreferences
    ) -> CriterionMatch:
        """Score interest overlap using Jaccard similarity."""
        if not prefs.interests:
            return self._not_applicable("interests", candidate.interests or None)

        if not candidate.interests:
            return self._missing_candidate_data("interests", prefs.interests)

        score, shared, missing = self._jaccard(prefs.interests, candidate.interests)

        if score >= 70:
            reason = f"Strong interest overlap: {shared[:3]}"
        elif score >= 30:
            reason = f"Some shared interests, missing: {missing[:3]}"
        else:
            reason = "Very few shared interests"

        return self._build(
            "interests", score, self._status_for_overlap(score), reason,
            candidate.interests, prefs.interests,
        )

    @staticmethod
    def _status_for_overlap(score: float) -> MatchStatus:
        """Overlap scores are naturally lower, so the bands are more forgiving."""
        if score >= 70:
            return MatchStatus.MATCH
        if score >= 30:
            return MatchStatus.PARTIAL_MATCH
        return MatchStatus.NO_MATCH

    # ------------------------------------------------------------------
    # Marriage expectations
    # ------------------------------------------------------------------

    def _score_marriage_timeline(
        self, candidate: UserProfile, prefs: PartnerPreferences
    ) -> CriterionMatch:
        """Score how soon both sides want to marry (document field 22)."""
        return self._score_ordinal(
            "marriage_timeline",
            candidate.marriage_timeline,
            prefs.marriage_timeline,
            MARRIAGE_TIMELINE_ORDER,
            "Marriage timeline",
            step_penalty=22.0,
        )

    def _score_children_preference(
        self, candidate: UserProfile, prefs: PartnerPreferences
    ) -> CriterionMatch:
        """Score attitude towards children (document field 23)."""
        return self._score_categorical(
            "children_preference",
            candidate.children_preference,
            prefs.children_preference,
            "Children preference",
            mismatch_score=25.0,
        )

    def _score_relocation(
        self, candidate: UserProfile, prefs: PartnerPreferences
    ) -> CriterionMatch:
        """Score willingness to relocate (document field 24)."""
        return self._score_categorical(
            "relocation",
            candidate.relocation,
            prefs.relocation,
            "Relocation willingness",
            mismatch_score=25.0,
        )

    def _score_career_expectation(
        self, candidate: UserProfile, prefs: PartnerPreferences
    ) -> CriterionMatch:
        """Score career expectations after marriage (document field 25)."""
        return self._score_categorical(
            "career_expectation",
            candidate.career_expectation,
            prefs.career_expectation,
            "Career expectation",
            mismatch_score=25.0,
        )
