"""Unit tests for the Scoring Engine."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from models.schema import (
    DifficultyLevel,
    InteractionEvent,
    QuestionCategory,
    QuestionResult,
    ScoringConfig,
)
from engine.scoring import ScoringEngine


@pytest.fixture
def default_config():
    return ScoringConfig()


@pytest.fixture
def engine(default_config):
    return ScoringEngine(default_config)


def _make_event(
    qid="Q1",
    difficulty="medium",
    category="technical",
    response="A reasonable answer with enough detail.",
    time_taken=120,
    max_time=300,
    relevance=7.0,
    completeness=7.0,
    accuracy=7.0,
    communication=7.0,
    is_follow_up=False,
):
    return InteractionEvent(
        question_id=qid,
        question_text="Test question",
        difficulty_level=DifficultyLevel.from_str(difficulty),
        category=QuestionCategory.from_str(category),
        candidate_response=response,
        time_taken_seconds=time_taken,
        max_time_seconds=max_time,
        is_follow_up=is_follow_up,
        relevance_score=relevance,
        completeness_score=completeness,
        accuracy_score=accuracy,
        communication_score=communication,
    )


class TestPerQuestionScoring:
    """Test individual question scoring."""

    def test_basic_scoring_produces_nonzero(self, engine):
        event = _make_event()
        result = engine.score_question(event)
        assert result.final_score > 0
        assert result.had_response is True

    def test_no_response_scores_zero(self, engine):
        event = _make_event(response=None)
        result = engine.score_question(event)
        assert result.final_score == 0.0
        assert result.had_response is False

    def test_empty_response_scores_zero(self, engine):
        event = _make_event(response="")
        result = engine.score_question(event)
        assert result.final_score == 0.0

    def test_whitespace_response_scores_zero(self, engine):
        event = _make_event(response="   ")
        result = engine.score_question(event)
        assert result.final_score == 0.0


class TestDifficultyMultiplier:
    """Test difficulty multiplier application."""

    def test_easy_multiplier(self, engine):
        event = _make_event(difficulty="easy")
        result = engine.score_question(event)
        assert result.difficulty_multiplier == 0.8

    def test_medium_multiplier(self, engine):
        event = _make_event(difficulty="medium")
        result = engine.score_question(event)
        assert result.difficulty_multiplier == 1.0

    def test_hard_multiplier(self, engine):
        event = _make_event(difficulty="hard")
        result = engine.score_question(event)
        assert result.difficulty_multiplier == 1.3

    def test_hard_scores_higher_max(self, engine):
        easy = engine.score_question(_make_event(difficulty="easy"))
        hard = engine.score_question(_make_event(difficulty="hard"))
        assert hard.max_possible > easy.max_possible

    def test_same_answers_hard_vs_easy(self, engine):
        """Same quality answers should yield higher final_score for hard."""
        easy = engine.score_question(
            _make_event(difficulty="easy", relevance=8, completeness=8, accuracy=8, communication=8)
        )
        hard = engine.score_question(
            _make_event(difficulty="hard", relevance=8, completeness=8, accuracy=8, communication=8)
        )
        assert hard.final_score > easy.final_score


class TestTimeModifier:
    """Test time efficiency modifier logic."""

    def test_normal_time_no_penalty(self, engine):
        event = _make_event(time_taken=150, max_time=300)  # 50%
        result = engine.score_question(event)
        assert result.time_modifier == 1.0

    def test_too_fast_penalty(self, engine):
        event = _make_event(time_taken=20, max_time=300)  # ~6.7%
        result = engine.score_question(event)
        assert result.time_modifier == 0.85

    def test_slow_penalty(self, engine):
        event = _make_event(time_taken=280, max_time=300)  # ~93%
        result = engine.score_question(event)
        assert result.time_modifier == 0.90

    def test_overtime_penalty(self, engine):
        event = _make_event(time_taken=350, max_time=300)  # >100%
        result = engine.score_question(event)
        assert result.time_modifier == 0.70

    def test_exactly_at_fast_boundary(self, engine):
        # At exactly 30% → should NOT be penalized (not < 0.30)
        event = _make_event(time_taken=90, max_time=300)  # exactly 30%
        result = engine.score_question(event)
        assert result.time_modifier == 1.0


class TestWeightedScoring:
    """Test weighted criteria computation."""

    def test_all_tens_gives_max_raw_score(self, engine):
        event = _make_event(relevance=10, completeness=10, accuracy=10, communication=10)
        result = engine.score_question(event)
        # raw_score should be close to 10 (time efficiency adds its part)
        assert result.raw_score >= 9.0

    def test_all_zeros_gives_zero_raw(self, engine):
        event = _make_event(relevance=0, completeness=0, accuracy=0, communication=0)
        result = engine.score_question(event)
        # Only time_efficiency_weight (0.10) contributes, so raw > 0 but small
        assert result.raw_score < 2.0

    def test_higher_relevance_increases_score(self, engine):
        low = engine.score_question(_make_event(relevance=2))
        high = engine.score_question(_make_event(relevance=9))
        assert high.final_score > low.final_score


class TestSkillMatch:
    """Test skill matching computation."""

    def test_full_match(self, engine):
        ratio, matched = engine.compute_skill_match(
            ["Python", "SQL", "Docker"],
            ["Python", "SQL", "Docker"],
        )
        assert ratio == 1.0
        assert len(matched) == 3

    def test_partial_match(self, engine):
        ratio, matched = engine.compute_skill_match(
            ["Python", "Java"],
            ["Python", "SQL", "Docker"],
        )
        assert abs(ratio - 1 / 3) < 0.01
        assert "Python" in matched

    def test_no_match(self, engine):
        ratio, matched = engine.compute_skill_match(
            ["Go", "Rust"],
            ["Python", "SQL"],
        )
        assert ratio == 0.0
        assert matched == []

    def test_case_insensitive(self, engine):
        ratio, _ = engine.compute_skill_match(
            ["python", "SQL"],
            ["Python", "sql"],
        )
        assert ratio == 1.0

    def test_empty_required_skills(self, engine):
        ratio, _ = engine.compute_skill_match(["Python"], [])
        assert ratio == 1.0


class TestCategoryBreakdown:
    """Test category aggregation."""

    def test_single_category(self, engine):
        results = [
            QuestionResult("Q1", "technical", "medium", 7.0, 1.0, 1.0, 7.0, 10.0, False, 100, True),
            QuestionResult("Q2", "technical", "hard", 8.0, 1.3, 1.0, 10.4, 13.0, False, 200, True),
        ]
        breakdowns = engine.compute_category_breakdown(results)
        assert len(breakdowns) == 1
        assert breakdowns[0].category == "technical"
        assert breakdowns[0].questions_count == 2

    def test_multiple_categories(self, engine):
        results = [
            QuestionResult("Q1", "technical", "medium", 7.0, 1.0, 1.0, 7.0, 10.0, False, 100, True),
            QuestionResult("Q2", "behavioral", "easy", 6.0, 0.8, 1.0, 4.8, 8.0, False, 90, True),
        ]
        breakdowns = engine.compute_category_breakdown(results)
        assert len(breakdowns) == 2
        cats = {b.category for b in breakdowns}
        assert "technical" in cats
        assert "behavioral" in cats


class TestInterviewReadinessScore:
    """Test final IRS computation."""

    def test_perfect_score_approaches_100(self, engine):
        results = [
            QuestionResult("Q1", "technical", "hard", 10.0, 1.3, 1.0, 13.0, 13.0, False, 200, True),
        ]
        irs = engine.compute_interview_readiness_score(results, skill_match_ratio=1.0)
        assert irs >= 100.0  # base 100 + bonus

    def test_zero_score_for_no_results(self, engine):
        irs = engine.compute_interview_readiness_score([], skill_match_ratio=0.5)
        assert irs == 0.0

    def test_skill_match_adds_bonus(self, engine):
        results = [
            QuestionResult("Q1", "technical", "medium", 7.0, 1.0, 1.0, 7.0, 10.0, False, 150, True),
        ]
        no_match = engine.compute_interview_readiness_score(results, skill_match_ratio=0.0)
        full_match = engine.compute_interview_readiness_score(results, skill_match_ratio=1.0)
        assert full_match > no_match

    def test_irs_capped_at_100(self, engine):
        results = [
            QuestionResult("Q1", "technical", "hard", 10.0, 1.3, 1.0, 13.0, 13.0, False, 200, True),
        ]
        irs = engine.compute_interview_readiness_score(results, skill_match_ratio=1.0)
        assert irs <= 100.0
