"""Tests for Lead Scoring Agent — rule-based fallback scoring logic."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.lead_scoring import _fallback_score
from app.models.lead import Lead, Activity
from app.models.user import User


def _make_user_id() -> str:
    return str(uuid.uuid4())


def _make_lead(**overrides) -> Lead:
    """Create a Lead with sensible defaults — fully detached from DB."""
    defaults = {
        "id": str(uuid.uuid4()),
        "name": "Test Lead",
        "phone": "0901234567",
        "email": "test@example.com",
        "source": "facebook",
        "property_type": "townhouse",
        "area_sqm": 120.0,
        "estimated_budget": 1_500_000_000,
        "stage": "new",
        "priority": "medium",
        "created_at": datetime.now(timezone.utc) - timedelta(days=5),
        "last_contacted_at": datetime.now(timezone.utc) - timedelta(days=2),
    }
    defaults.update(overrides)
    return Lead(**defaults)


def _make_activity(lead_id: str, user_id: str, **overrides) -> Activity:
    defaults = {
        "id": str(uuid.uuid4()),
        "lead_id": lead_id,
        "user_id": user_id,
        "type": "call",
        "content": "Called lead",
        "created_at": datetime.now(timezone.utc),
    }
    defaults.update(overrides)
    return Activity(**defaults)


class TestFallbackScoring:
    """Test the rule-based _fallback_score function directly (no DB needed)."""

    def test_high_budget_lead_scores_high(self):
        lead = _make_lead(
            estimated_budget=3_000_000_000,  # >= 2 ty -> 25 pts
            source="referral",                 # 20 pts
            property_type="villa",             # 20 pts
            area_sqm=250,                      # >= 200 -> 15 pts
        )
        uid = _make_user_id()
        activities = [_make_activity(lead.id, uid) for _ in range(5)]  # 5 acts -> 15 pts

        result = _fallback_score(lead, activities)
        score = result["score"]
        # Budget(25) + Source(20) + Prop(20) + Area(15) + Eng(15) + Recency(5) + stage_bonus(10) + referral_villa_bonus(5) = 115, clamped to 100
        assert score == 100
        assert len(result["factors"]) == 6
        assert isinstance(result["recommendations"], list)

    def test_low_budget_no_activity_scores_low(self):
        lead = _make_lead(
            estimated_budget=200_000_000,   # < 500 trieu -> 5 pts
            source="tiktok",                 # 5 pts
            property_type="apartment",       # 8 pts
            area_sqm=60,                     # < 100 -> 5 pts
            stage="new",
            created_at=datetime.now(timezone.utc) - timedelta(days=30),
            last_contacted_at=datetime.now(timezone.utc) - timedelta(days=20),
        )
        result = _fallback_score(lead, [])
        score = result["score"]
        # Budget(5) + Source(5) + Prop(8) + Area(5) + Eng(3) + Recency(1) = 27
        # No stage bonus for "new" (only "potential" or "signed_design")
        # days_since_last > 14 -> -10
        assert score == 17  # 27 - 10
        assert score >= 0

    def test_score_clamped_to_0_100(self):
        lead = _make_lead(
            estimated_budget=None,
            source="other",
            property_type=None,
            area_sqm=None,
            stage="new",
            created_at=datetime.now(timezone.utc) - timedelta(days=60),
            last_contacted_at=datetime.now(timezone.utc) - timedelta(days=30),
        )
        result = _fallback_score(lead, [])
        assert 0 <= result["score"] <= 100

    def test_referral_villa_bonus(self):
        lead = _make_lead(
            estimated_budget=1_500_000_000,
            source="referral",
            property_type="villa",
            area_sqm=200,
            stage="potential",
            created_at=datetime.now(timezone.utc),
            last_contacted_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        uid = _make_user_id()
        activities = [_make_activity(lead.id, uid) for _ in range(5)]

        result = _fallback_score(lead, activities)
        # Budget(25) + Source(20) + Prop(20) + Area(15) + Eng(15) + Recency(5)
        # + stage_bonus(10) + referral_villa_bonus(5) = 115, clamped to 100
        assert result["score"] == 100

    def test_engagement_tiers(self):
        uid = _make_user_id()
        lead = _make_lead()

        # 0 activities -> eng_score = 3
        result0 = _fallback_score(lead, [])
        eng0 = next(f for f in result0["factors"] if f["name"] == "engagement")
        assert "0 hoat dong" in eng0["value"]

        # 2 activities -> eng_score = 8
        acts2 = [_make_activity(lead.id, uid) for _ in range(2)]
        result2 = _fallback_score(lead, acts2)
        eng2 = next(f for f in result2["factors"] if f["name"] == "engagement")
        assert "2 hoat dong" in eng2["value"]
        assert result2["score"] > result0["score"]

        # 5+ activities -> eng_score = 15
        acts5 = [_make_activity(lead.id, uid) for _ in range(5)]
        result5 = _fallback_score(lead, acts5)
        assert result5["score"] > result2["score"]

    def test_recency_tiers(self):
        uid = _make_user_id()

        # Recent (< 3 days) -> recency_score = 5
        lead_recent = _make_lead(
            last_contacted_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        r_recent = _fallback_score(lead_recent, [_make_activity(lead_recent.id, uid)])
        rec_recent = next(f for f in r_recent["factors"] if f["name"] == "recency")
        assert rec_recent["weight"] == 0.05

        # Old (> 7 days) -> recency_score = 1
        lead_old = _make_lead(
            last_contacted_at=datetime.now(timezone.utc) - timedelta(days=10),
        )
        r_old = _fallback_score(lead_old, [_make_activity(lead_old.id, uid)])
        assert r_recent["score"] > r_old["score"]

    def test_source_scores(self):
        for source, min_expected in [("referral", 80), ("website", 70), ("facebook", 60), ("tiktok", 50)]:
            lead = _make_lead(source=source)
            result = _fallback_score(lead, [])
            assert result["score"] >= min_expected - 30  # generous bounds for composite

    def test_property_type_scores(self):
        lead_villa = _make_lead(property_type="villa")
        result_villa = _fallback_score(lead_villa, [])
        prop_villa = next(f for f in result_villa["factors"] if f["name"] == "property_type")
        assert "Villa" in prop_villa["value"]

        lead_apartment = _make_lead(property_type="apartment")
        result_apartment = _fallback_score(lead_apartment, [])
        assert result_villa["score"] > result_apartment["score"]

    def test_recommendations_generated(self):
        lead = _make_lead(source="referral", property_type="villa", stage="new", area_sqm=None)
        result = _fallback_score(lead, [])
        recs = result["recommendations"]
        assert isinstance(recs, list)
        assert len(recs) >= 1
        # Villa lead should get villa recommendation
        assert any("villa" in r.lower() or "biet thu" in r.lower() for r in recs)

    def test_all_factor_names_present(self):
        lead = _make_lead()
        result = _fallback_score(lead, [])
        factor_names = {f["name"] for f in result["factors"]}
        assert factor_names == {"budget", "source", "property_type", "area", "engagement", "recency"}

    def test_stage_potential_bonus(self):
        lead_potential = _make_lead(stage="potential")
        lead_new = _make_lead(stage="new")
        r_potential = _fallback_score(lead_potential, [])
        r_new = _fallback_score(lead_new, [])
        assert r_potential["score"] == r_new["score"] + 10

    def test_signed_design_bonus(self):
        lead_signed = _make_lead(stage="signed_design")
        lead_new = _make_lead(stage="new")
        r_signed = _fallback_score(lead_signed, [])
        r_new = _fallback_score(lead_new, [])
        assert r_signed["score"] == r_new["score"] + 10

    def test_overdue_penalty(self):
        lead_recent = _make_lead(
            created_at=datetime.now(timezone.utc),
            last_contacted_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        lead_overdue = _make_lead(
            created_at=datetime.now(timezone.utc),
            last_contacted_at=datetime.now(timezone.utc) - timedelta(days=20),
        )
        r_recent = _fallback_score(lead_recent, [])
        r_overdue = _fallback_score(lead_overdue, [])
        # Overdue has: -10 penalty + lower recency score (1 vs 5)
        assert r_overdue["score"] < r_recent["score"]
        assert r_recent["score"] - r_overdue["score"] >= 10
