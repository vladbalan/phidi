"""
Unit tests for reranking and scoring logic.
Tests score_candidate, rerank_candidates, load_weights.
Verifies weighted scoring, fuzzy matching, social scoring fix.
"""
from __future__ import annotations

import pytest
from src.api.rerank import (
    score_candidate,
    rerank_candidates,
    load_weights,
    DEFAULT_WEIGHTS,
)


class TestLoadWeights:
    """Test weight configuration loading."""

    def test_load_weights_returns_dict(self):
        """Test that load_weights returns a dictionary."""
        weights = load_weights()
        assert isinstance(weights, dict)

    def test_load_weights_has_required_keys(self):
        """Test that weights contain all required keys."""
        weights = load_weights()
        required_keys = ["domain_weight", "name_weight", "phone_weight", "social_weight"]
        for key in required_keys:
            assert key in weights

    def test_weights_sum_to_one(self):
        """Test that scoring weights sum to approximately 1.0."""
        weights = load_weights()
        total = (
            weights["domain_weight"]
            + weights["name_weight"]
            + weights["phone_weight"]
            + weights["social_weight"]
        )
        assert abs(total - 1.0) < 0.01  # Allow small floating point error

    def test_weights_are_positive(self):
        """Test that all weights are positive."""
        weights = load_weights()
        assert weights["domain_weight"] > 0
        assert weights["name_weight"] > 0
        assert weights["phone_weight"] > 0
        assert weights["social_weight"] > 0

    def test_load_weights_includes_threshold(self):
        """Test that min_confidence_threshold is loaded."""
        weights = load_weights()
        assert "min_confidence_threshold" in weights
        assert isinstance(weights["min_confidence_threshold"], (int, float))
        assert 0.0 <= weights["min_confidence_threshold"] <= 1.0

    def test_default_weights_fallback(self):
        """Test that DEFAULT_WEIGHTS are used when file missing."""
        weights = load_weights(path="/nonexistent/path/weights.yaml")
        assert weights["domain_weight"] == DEFAULT_WEIGHTS["domain_weight"]
        assert weights["name_weight"] == DEFAULT_WEIGHTS["name_weight"]


class TestScoreCandidate:
    """Test individual candidate scoring."""

    def test_perfect_domain_match(self):
        """Test scoring with perfect domain match."""
        inp = {"domain": "example.com", "company_name": "", "phone": None, "facebook": None, "instagram": None}
        cand = {"domain": "example.com", "company_name": "", "phones": [], "facebook": None, "instagram": None}
        weights = DEFAULT_WEIGHTS
        
        score, breakdown = score_candidate(inp, cand, weights)
        
        assert breakdown["domain"] == 1.0
        assert score >= 0.4  # Domain weight is 0.45

    def test_perfect_domain_and_name_match(self):
        """Test scoring with perfect domain and name match."""
        inp = {"domain": "example.com", "company_name": "example corp", "phone": None, "facebook": None, "instagram": None}
        cand = {"domain": "example.com", "company_name": "example corp", "phones": [], "facebook": None, "instagram": None}
        weights = DEFAULT_WEIGHTS
        
        score, breakdown = score_candidate(inp, cand, weights)
        
        assert breakdown["domain"] == 1.0
        assert breakdown["name"] == 1.0
        assert score >= 0.7  # domain (0.45) + name (0.30)

    def test_fuzzy_domain_match(self):
        """Test fuzzy matching on similar domains."""
        inp = {"domain": "example.com", "company_name": "", "phone": None, "facebook": None, "instagram": None}
        cand = {"domain": "examples.com", "company_name": "", "phones": [], "facebook": None, "instagram": None}
        weights = DEFAULT_WEIGHTS
        
        score, breakdown = score_candidate(inp, cand, weights)
        
        # Should have partial domain match (fuzzy)
        assert 0.0 < breakdown["domain"] < 1.0
        assert breakdown["domain"] > 0.8  # Very similar

    def test_phone_exact_match(self):
        """Test phone number exact matching."""
        inp = {"domain": "", "company_name": "", "phone": "+15551234567", "facebook": None, "instagram": None}
        cand = {"domain": "", "company_name": "", "phones": ["+15551234567"], "facebook": None, "instagram": None}
        weights = DEFAULT_WEIGHTS
        
        score, breakdown = score_candidate(inp, cand, weights)
        
        assert breakdown["phone"] == 1.0

    def test_phone_no_match(self):
        """Test phone number mismatch."""
        inp = {"domain": "", "company_name": "", "phone": "+15551234567", "facebook": None, "instagram": None}
        cand = {"domain": "", "company_name": "", "phones": ["+15559876543"], "facebook": None, "instagram": None}
        weights = DEFAULT_WEIGHTS
        
        score, breakdown = score_candidate(inp, cand, weights)
        
        assert breakdown["phone"] == 0.0

    def test_social_match_both_present(self):
        """Test social scoring when both input and candidate have Facebook."""
        inp = {"domain": "", "company_name": "", "phone": None, "facebook": "facebook.com/test", "instagram": None}
        cand = {"domain": "", "company_name": "", "phones": [], "facebook": "facebook.com/test", "instagram": None}
        weights = DEFAULT_WEIGHTS
        
        score, breakdown = score_candidate(inp, cand, weights)
        
        assert breakdown["social"] == 1.0

    def test_social_no_penalty_when_candidate_missing(self):
        """Test that candidate without social data isn't penalized (bug fix)."""
        inp = {"domain": "test.com", "company_name": "test", "phone": None, "facebook": "facebook.com/test", "instagram": None}
        cand = {"domain": "test.com", "company_name": "test", "phones": [], "facebook": None, "instagram": None}
        weights = DEFAULT_WEIGHTS
        
        score, breakdown = score_candidate(inp, cand, weights)
        
        # Social should be neutral (0.5) not zero
        assert breakdown["social"] == 0.5
        # Total score should be high due to domain match
        assert score >= 0.7

    def test_social_neutral_when_no_comparison_possible(self):
        """Test that social score is neutral when neither side has data."""
        inp = {"domain": "test.com", "company_name": "test", "phone": None, "facebook": None, "instagram": None}
        cand = {"domain": "test.com", "company_name": "test", "phones": [], "facebook": None, "instagram": None}
        weights = DEFAULT_WEIGHTS
        
        score, breakdown = score_candidate(inp, cand, weights)
        
        assert breakdown["social"] == 0.5

    def test_instagram_matching(self):
        """Test Instagram URL matching."""
        inp = {"domain": "", "company_name": "", "phone": None, "facebook": None, "instagram": "instagram.com/test"}
        cand = {"domain": "", "company_name": "", "phones": [], "facebook": None, "instagram": "instagram.com/test"}
        weights = DEFAULT_WEIGHTS
        
        score, breakdown = score_candidate(inp, cand, weights)
        
        assert breakdown["social"] == 1.0

    def test_multiple_social_platforms(self):
        """Test scoring with both Facebook and Instagram."""
        inp = {
            "domain": "",
            "company_name": "",
            "phone": None,
            "facebook": "facebook.com/test",
            "instagram": "instagram.com/test"
        }
        cand = {
            "domain": "",
            "company_name": "",
            "phones": [],
            "facebook": "facebook.com/test",
            "instagram": "instagram.com/test"
        }
        weights = DEFAULT_WEIGHTS
        
        score, breakdown = score_candidate(inp, cand, weights)
        
        assert breakdown["social"] == 1.0  # Both match

    def test_partial_social_match(self):
        """Test scoring when one social matches and one doesn't."""
        inp = {
            "domain": "",
            "company_name": "",
            "phone": None,
            "facebook": "facebook.com/test1",
            "instagram": "instagram.com/test"
        }
        cand = {
            "domain": "",
            "company_name": "",
            "phones": [],
            "facebook": "facebook.com/test2",
            "instagram": "instagram.com/test"
        }
        weights = DEFAULT_WEIGHTS
        
        score, breakdown = score_candidate(inp, cand, weights)
        
        assert breakdown["social"] == 0.5  # 1/2 matches

    def test_score_breakdown_structure(self):
        """Test that breakdown contains all expected keys."""
        inp = {"domain": "test.com", "company_name": "test", "phone": "+15551234567", "facebook": "facebook.com/test", "instagram": None}
        cand = {"domain": "test.com", "company_name": "test", "phones": [], "facebook": None, "instagram": None}
        weights = DEFAULT_WEIGHTS
        
        score, breakdown = score_candidate(inp, cand, weights)
        
        assert "domain" in breakdown
        assert "name" in breakdown
        assert "phone" in breakdown
        assert "social" in breakdown
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0


class TestRerankCandidates:
    """Test candidate reranking logic."""

    def test_rerank_empty_list(self):
        """Test reranking with no candidates."""
        inp = {"domain": "test.com", "company_name": "test", "phone": None, "facebook": None, "instagram": None}
        candidates = []
        
        ranked = rerank_candidates(inp, candidates)
        
        assert ranked == []

    def test_rerank_single_candidate(self):
        """Test reranking with single candidate."""
        inp = {"domain": "test.com", "company_name": "test", "phone": None, "facebook": None, "instagram": None}
        candidates = [
            {"domain": "test.com", "company_name": "test corp", "phones": [], "facebook": None, "instagram": None}
        ]
        
        ranked = rerank_candidates(inp, candidates)
        
        assert len(ranked) == 1
        assert "candidate" in ranked[0]
        assert "score" in ranked[0]
        assert "breakdown" in ranked[0]

    def test_rerank_sorts_by_score_descending(self):
        """Test that candidates are sorted by score (highest first)."""
        inp = {"domain": "test.com", "company_name": "test", "phone": None, "facebook": None, "instagram": None}
        candidates = [
            {"domain": "other.com", "company_name": "other", "phones": [], "facebook": None, "instagram": None},
            {"domain": "test.com", "company_name": "test", "phones": [], "facebook": None, "instagram": None},
            {"domain": "another.com", "company_name": "test", "phones": [], "facebook": None, "instagram": None},
        ]
        
        ranked = rerank_candidates(inp, candidates)
        
        # Perfect domain match should be first
        assert ranked[0]["candidate"]["domain"] == "test.com"
        # Scores should be descending
        for i in range(len(ranked) - 1):
            assert ranked[i]["score"] >= ranked[i + 1]["score"]

    def test_rerank_preserves_all_candidates(self):
        """Test that all candidates are preserved."""
        inp = {"domain": "test.com", "company_name": "test", "phone": None, "facebook": None, "instagram": None}
        candidates = [
            {"domain": f"test{i}.com", "company_name": f"test{i}", "phones": [], "facebook": None, "instagram": None}
            for i in range(10)
        ]
        
        ranked = rerank_candidates(inp, candidates)
        
        assert len(ranked) == 10

    def test_rerank_output_structure(self):
        """Test that rerank output has correct structure."""
        inp = {"domain": "test.com", "company_name": "test", "phone": None, "facebook": None, "instagram": None}
        candidates = [
            {"domain": "test.com", "company_name": "test", "phones": [], "facebook": None, "instagram": None}
        ]
        
        ranked = rerank_candidates(inp, candidates)
        
        assert len(ranked) == 1
        item = ranked[0]
        assert isinstance(item, dict)
        assert "candidate" in item
        assert "score" in item
        assert "breakdown" in item
        assert isinstance(item["candidate"], dict)
        assert isinstance(item["score"], float)
        assert isinstance(item["breakdown"], dict)

    def test_rerank_with_custom_weights(self):
        """Test reranking with custom weights."""
        inp = {"domain": "test.com", "company_name": "test", "phone": None, "facebook": None, "instagram": None}
        candidates = [
            {"domain": "test.com", "company_name": "test", "phones": [], "facebook": None, "instagram": None}
        ]
        
        # Should not crash with custom weights path
        ranked = rerank_candidates(inp, candidates, weights_path="/nonexistent/path.yaml")
        
        assert len(ranked) == 1

    def test_rerank_identical_scores(self):
        """Test reranking with candidates having identical scores."""
        inp = {"domain": "unknown.com", "company_name": "unknown", "phone": None, "facebook": None, "instagram": None}
        candidates = [
            {"domain": "test1.com", "company_name": "test1", "phones": [], "facebook": None, "instagram": None},
            {"domain": "test2.com", "company_name": "test2", "phones": [], "facebook": None, "instagram": None},
            {"domain": "test3.com", "company_name": "test3", "phones": [], "facebook": None, "instagram": None},
        ]
        
        ranked = rerank_candidates(inp, candidates)
        
        # Should handle gracefully (stable sort)
        assert len(ranked) == 3


class TestScoringEdgeCases:
    """Test edge cases in scoring logic."""

    def test_missing_candidate_fields(self):
        """Test scoring when candidate is missing fields."""
        inp = {"domain": "test.com", "company_name": "test", "phone": "+15551234567", "facebook": "facebook.com/test", "instagram": None}
        cand = {"domain": "test.com"}  # Missing most fields
        weights = DEFAULT_WEIGHTS
        
        score, breakdown = score_candidate(inp, cand, weights)
        
        # Should handle gracefully
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0

    def test_empty_strings_in_candidate(self):
        """Test scoring with empty strings."""
        inp = {"domain": "test.com", "company_name": "test", "phone": None, "facebook": None, "instagram": None}
        cand = {"domain": "", "company_name": "", "phones": [], "facebook": "", "instagram": ""}
        weights = DEFAULT_WEIGHTS
        
        score, breakdown = score_candidate(inp, cand, weights)
        
        assert breakdown["domain"] == 0.0
        assert breakdown["name"] == 0.0

    def test_none_values_in_input(self):
        """Test scoring with None values in input."""
        inp = {"domain": None, "company_name": None, "phone": None, "facebook": None, "instagram": None}
        cand = {"domain": "test.com", "company_name": "test", "phones": [], "facebook": None, "instagram": None}
        weights = DEFAULT_WEIGHTS
        
        score, breakdown = score_candidate(inp, cand, weights)
        
        # Should handle gracefully without crashing
        assert isinstance(score, float)

    def test_special_characters_in_names(self):
        """Test fuzzy matching with special characters."""
        inp = {"domain": "", "company_name": "test & co.", "phone": None, "facebook": None, "instagram": None}
        cand = {"domain": "", "company_name": "test and co", "phones": [], "facebook": None, "instagram": None}
        weights = DEFAULT_WEIGHTS
        
        score, breakdown = score_candidate(inp, cand, weights)
        
        # Should have some similarity
        assert breakdown["name"] > 0.5

    def test_case_insensitive_matching(self):
        """Test that matching is case-insensitive for names (domains normalized in app)."""
        # Note: Domain normalization happens in app.py before scoring
        # So we test with already normalized domains here
        inp = {"domain": "test.com", "company_name": "TEST COMPANY", "phone": None, "facebook": None, "instagram": None}
        cand = {"domain": "test.com", "company_name": "test company", "phones": [], "facebook": None, "instagram": None}
        weights = DEFAULT_WEIGHTS
        
        score, breakdown = score_candidate(inp, cand, weights)
        
        assert breakdown["domain"] == 1.0  # Exact match after normalization
        assert breakdown["name"] == 1.0  # Case-insensitive name matching
