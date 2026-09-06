"""
Unit tests for the mutual (two-way) matchmaking engine.

Covers the behaviour that distinguishes mutual matching from one-way scoring:
- both directions are scored independently,
- the mutual score sits between the two directions,
- a failure on EITHER side rejects the pair,
- a candidate without preferences falls back to one-way scoring,
- unspecified preferences are excluded rather than scored as neutral.
"""

from __future__ import annotations

import pytest

from matchmaking.config import MatchmakingConfig
from matchmaking.processing.mutual_engine import MutualMatchingEngine
from matchmaking.schemas import (
    AgeRange,
    CareerExpectation,
    ChildrenPreference,
    EducationLevel,
    Gender,
    IncomeRange,
    Location,
    MaritalStatus,
    MatchDirection,
    MatchStatus,
    ModelConfidence,
    PartnerPreferences,
    ReligiousPractice,
    UserProfile,
)


def _engine() -> MutualMatchingEngine:
    return MutualMatchingEngine(MatchmakingConfig(ai_enabled=False))


def _man(**overrides) -> UserProfile:
    data = dict(
        user_id="u_man",
        name="Man",
        gender=Gender.MALE,
        age=30,
        height_cm=178,
        marital_status=MaritalStatus.NEVER_MARRIED,
        religion="Islam",
        sect="Sunni",
        religious_practice=ReligiousPractice.PRACTICING,
        education=EducationLevel.MASTERS,
        profession="Software Engineer",
        monthly_income=350000,
        location=Location(city="Islamabad", country="Pakistan"),
        smoking=False,
        diet="Halal",
        children_preference=ChildrenPreference.WANT_CHILDREN,
        career_expectation=CareerExpectation.CONTINUE_CAREER,
        interests=["Travel", "Reading"],
    )
    data.update(overrides)
    return UserProfile(**data)


def _woman(**overrides) -> UserProfile:
    data = dict(
        user_id="u_woman",
        name="Woman",
        gender=Gender.FEMALE,
        age=27,
        height_cm=163,
        marital_status=MaritalStatus.NEVER_MARRIED,
        religion="Islam",
        sect="Sunni",
        religious_practice=ReligiousPractice.PRACTICING,
        education=EducationLevel.MASTERS,
        profession="Doctor",
        monthly_income=220000,
        location=Location(city="Islamabad", country="Pakistan"),
        smoking=False,
        diet="Halal",
        children_preference=ChildrenPreference.WANT_CHILDREN,
        career_expectation=CareerExpectation.CONTINUE_CAREER,
        interests=["Travel", "Reading"],
    )
    data.update(overrides)
    return UserProfile(**data)


def _wants_woman(**overrides) -> PartnerPreferences:
    data = dict(
        gender=Gender.FEMALE,
        age_range=AgeRange(min=24, max=30),
        religion=["Islam"],
        sect=["Sunni"],
        marital_status=[MaritalStatus.NEVER_MARRIED],
        min_education=EducationLevel.BACHELORS,
        location=["Islamabad"],
        smoking=False,
    )
    data.update(overrides)
    return PartnerPreferences(**data)


def _wants_man(**overrides) -> PartnerPreferences:
    data = dict(
        gender=Gender.MALE,
        age_range=AgeRange(min=28, max=35),
        religion=["Islam"],
        sect=["Sunni"],
        marital_status=[MaritalStatus.NEVER_MARRIED],
        min_education=EducationLevel.MASTERS,
        location=["Islamabad"],
        smoking=False,
    )
    data.update(overrides)
    return PartnerPreferences(**data)


class TestBothDirectionsAreScored:
    def test_two_way_result_when_candidate_has_preferences(self):
        candidate = _woman(partner_preferences=_wants_man())
        result = _engine().evaluate_pair(_man(), _wants_woman(), candidate)

        assert result.your_preferences_match.evaluated is True
        assert result.their_preferences_match.evaluated is True
        assert result.your_preferences_match.direction == (
            MatchDirection.USER_TO_CANDIDATE
        )
        assert result.their_preferences_match.direction == (
            MatchDirection.CANDIDATE_TO_USER
        )

    def test_mutual_score_lies_between_the_two_directions(self):
        # She is a great fit for him; he is a poor fit for her (wrong city).
        candidate = _woman(
            partner_preferences=_wants_man(location=["Karachi"]),
        )
        result = _engine().evaluate_pair(_man(), _wants_woman(), candidate)

        forward = result.your_preferences_match.score
        reverse = result.their_preferences_match.score
        assert forward > reverse
        # The mutual score must reflect BOTH sides, not just the user's view.
        assert reverse <= result.match_score <= forward
        assert result.match_score < forward

    def test_score_balance_reports_the_gap(self):
        candidate = _woman(partner_preferences=_wants_man(location=["Karachi"]))
        result = _engine().evaluate_pair(_man(), _wants_woman(), candidate)
        expected = abs(
            result.your_preferences_match.score
            - result.their_preferences_match.score
        )
        assert result.score_balance == expected


class TestOneWayFallback:
    def test_candidate_without_preferences_is_scored_one_way(self):
        candidate = _woman()  # no partner_preferences
        result = _engine().evaluate_pair(_man(), _wants_woman(), candidate)

        assert result.their_preferences_match.evaluated is False
        assert result.their_preferences_match.note is not None
        assert result.match_score == result.your_preferences_match.score

    def test_one_way_confidence_is_capped(self):
        two_way = _engine().evaluate_pair(
            _man(), _wants_woman(), _woman(partner_preferences=_wants_man())
        )
        one_way = _engine().evaluate_pair(_man(), _wants_woman(), _woman())
        assert one_way.confidence_score < two_way.confidence_score


class TestRejection:
    def test_failure_on_the_users_side_rejects(self):
        candidate = _woman(sect="Shia", partner_preferences=_wants_man())
        result = _engine().evaluate_pair(_man(), _wants_woman(), candidate)

        assert result.match_status == MatchStatus.REJECTED
        assert result.is_match is False

    def test_failure_on_the_candidates_side_also_rejects(self):
        # He satisfies everything she asks for except her sect requirement.
        candidate = _woman(partner_preferences=_wants_man(sect=["Shia"]))
        result = _engine().evaluate_pair(_man(), _wants_woman(), candidate)

        assert result.your_preferences_match.is_match is True
        assert result.their_preferences_match.failed_hard_constraints
        assert result.match_status == MatchStatus.REJECTED
        assert result.is_match is False

    def test_deal_breaker_on_either_side_rejects(self):
        smoker = _woman(smoking=True, partner_preferences=_wants_man())
        prefs = _wants_woman(deal_breakers=["smoking"])
        result = _engine().evaluate_pair(_man(), prefs, smoker)

        assert result.match_status == MatchStatus.REJECTED
        assert result.your_preferences_match.deal_breakers_violated == ["smoking"]


class TestUnspecifiedPreferencesAreExcluded:
    def test_only_requested_criteria_appear_in_the_breakdown(self):
        prefs = PartnerPreferences(
            gender=Gender.FEMALE,
            age_range=AgeRange(min=24, max=30),
            religion=["Islam"],
        )
        result = _engine().evaluate_pair(
            _man(), prefs, _woman(partner_preferences=_wants_man())
        )

        reported = {
            c.criterion for c in result.your_preferences_match.criterion_matches
        }
        assert reported == {"age", "religion"}
        assert all(c.applicable for c in result.your_preferences_match.criterion_matches)

    def test_sparse_preferences_do_not_drag_a_perfect_match_to_neutral(self):
        # Only two preferences, both perfectly satisfied -> near 100, not ~50.
        prefs = PartnerPreferences(
            age_range=AgeRange(min=24, max=30), religion=["Islam"]
        )
        result = _engine().evaluate_pair(_man(), prefs, _woman())
        assert result.your_preferences_match.score >= 95


class TestRanking:
    def test_list_is_ranked_by_mutual_score(self):
        good = _woman(user_id="good", partner_preferences=_wants_man())
        weak = _woman(
            user_id="weak",
            age=24,
            location=Location(city="Multan", country="Pakistan"),
            education=EducationLevel.HIGH_SCHOOL,
            partner_preferences=_wants_man(location=["Multan"]),
        )
        results, _ = _engine().match_against_list(
            _man(), _wants_woman(), [weak, good]
        )

        assert [r.candidate_id for r in results] == ["good", "weak"]
        assert results[0].match_score >= results[1].match_score

    def test_the_logged_in_user_is_never_matched_with_themselves(self):
        me = _man()
        results, warnings = _engine().match_against_list(
            me, _wants_woman(), [me, _woman(partner_preferences=_wants_man())]
        )
        assert [r.candidate_id for r in results] == ["u_woman"]
        assert any("same as the logged-in user" in w for w in warnings)

    def test_min_score_and_top_n_filters(self):
        candidates = [
            _woman(user_id=f"c{i}", partner_preferences=_wants_man())
            for i in range(3)
        ]
        results, _ = _engine().match_against_list(
            _man(), _wants_woman(), candidates, top_n=2
        )
        assert len(results) == 2

        results, _ = _engine().match_against_list(
            _man(), _wants_woman(), candidates, min_score=101
        )
        assert results == []


class TestModelConfidence:
    @pytest.mark.parametrize(
        "confidence,expected",
        [
            (90, ModelConfidence.HIGH),
            (75, ModelConfidence.HIGH),
            (60, ModelConfidence.MEDIUM),
            (50, ModelConfidence.MEDIUM),
            (20, ModelConfidence.LOW),
        ],
    )
    def test_confidence_buckets(self, confidence, expected):
        assert _engine()._confidence_bucket(confidence) == expected

    def test_result_reports_a_percentage_and_a_bucket(self):
        result = _engine().evaluate_pair(
            _man(), _wants_woman(), _woman(partner_preferences=_wants_man())
        )
        assert result.match_percentage == float(result.match_score)
        assert 0 <= result.match_percentage <= 100
        assert result.model_confidence in tuple(ModelConfidence)


class TestIncomeScoring:
    def test_income_within_the_preferred_band_scores_full(self):
        prefs = _wants_woman(
            income_range=IncomeRange(min=100000, max=300000, currency="PKR")
        )
        result = _engine().evaluate_pair(_man(), prefs, _woman())
        income = next(
            c
            for c in result.your_preferences_match.criterion_matches
            if c.criterion == "income"
        )
        assert income.score == 100.0

    def test_income_below_the_minimum_is_penalised_proportionally(self):
        prefs = _wants_woman(income_range=IncomeRange(min=440000))
        result = _engine().evaluate_pair(_man(), prefs, _woman())
        income = next(
            c
            for c in result.your_preferences_match.criterion_matches
            if c.criterion == "income"
        )
        assert income.score == pytest.approx(50.0, abs=1.0)

    def test_free_text_income_band_is_parsed(self):
        prefs = _wants_woman(income_range="150,000 - 300,000 PKR")
        result = _engine().evaluate_pair(_man(), prefs, _woman())
        income = next(
            c
            for c in result.your_preferences_match.criterion_matches
            if c.criterion == "income"
        )
        assert income.score == 100.0
