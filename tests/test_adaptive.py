"""Unit tests for the Adaptive Difficulty Engine."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from models.schema import DifficultyLevel, QuestionResult
from engine.adaptive import AdaptiveEngine


def _make_result(qid, final_score, max_possible, difficulty="medium"):
    return QuestionResult(
        question_id=qid,
        category="technical",
        difficulty=difficulty,
        raw_score=final_score,
        difficulty_multiplier=1.0,
        time_modifier=1.0,
        final_score=final_score,
        max_possible=max_possible,
        is_follow_up=False,
        time_taken_seconds=100,
        had_response=True,
    )


class TestDifficultyAdjustment:
    """Test sliding window difficulty adjustment logic."""

    def test_no_change_under_window_size(self):
        ae = AdaptiveEngine(initial_difficulty=DifficultyLevel.MEDIUM)
        results = [_make_result("Q1", 9.0, 10.0), _make_result("Q2", 9.0, 10.0)]
        diff = ae.evaluate(results)
        assert diff == DifficultyLevel.MEDIUM  # need 3 results

    def test_upgrade_on_3_high_scores(self):
        ae = AdaptiveEngine(initial_difficulty=DifficultyLevel.MEDIUM)
        results = [
            _make_result("Q1", 8.0, 10.0),
            _make_result("Q2", 8.5, 10.0),
            _make_result("Q3", 9.0, 10.0),
        ]
        diff = ae.evaluate(results)
        assert diff == DifficultyLevel.HARD

    def test_downgrade_on_2_low_scores(self):
        ae = AdaptiveEngine(initial_difficulty=DifficultyLevel.MEDIUM)
        results = [
            _make_result("Q1", 2.0, 10.0),
            _make_result("Q2", 3.0, 10.0),
            _make_result("Q3", 7.0, 10.0),
        ]
        diff = ae.evaluate(results)
        assert diff == DifficultyLevel.EASY

    def test_no_change_on_mixed_scores(self):
        ae = AdaptiveEngine(initial_difficulty=DifficultyLevel.MEDIUM)
        results = [
            _make_result("Q1", 5.0, 10.0),
            _make_result("Q2", 6.0, 10.0),
            _make_result("Q3", 7.0, 10.0),
        ]
        diff = ae.evaluate(results)
        assert diff == DifficultyLevel.MEDIUM

    def test_upgrade_capped_at_hard(self):
        ae = AdaptiveEngine(initial_difficulty=DifficultyLevel.HARD)
        results = [
            _make_result("Q1", 9.0, 10.0),
            _make_result("Q2", 9.0, 10.0),
            _make_result("Q3", 9.0, 10.0),
        ]
        diff = ae.evaluate(results)
        assert diff == DifficultyLevel.HARD

    def test_downgrade_capped_at_easy(self):
        ae = AdaptiveEngine(initial_difficulty=DifficultyLevel.EASY)
        results = [
            _make_result("Q1", 1.0, 10.0),
            _make_result("Q2", 2.0, 10.0),
            _make_result("Q3", 5.0, 10.0),
        ]
        diff = ae.evaluate(results)
        assert diff == DifficultyLevel.EASY

    def test_adjustment_recorded_in_trace(self):
        ae = AdaptiveEngine(initial_difficulty=DifficultyLevel.EASY)
        results = [
            _make_result("Q1", 8.0, 10.0),
            _make_result("Q2", 9.0, 10.0),
            _make_result("Q3", 8.5, 10.0),
        ]
        ae.evaluate(results)
        assert len(ae.adjustments) == 1
        assert ae.adjustments[0].previous_difficulty == "easy"
        assert ae.adjustments[0].new_difficulty == "medium"

    def test_multiple_adjustments_across_window(self):
        ae = AdaptiveEngine(initial_difficulty=DifficultyLevel.EASY)
        # Window 1: all high → upgrade to MEDIUM
        results = [
            _make_result("Q1", 8.0, 10.0),
            _make_result("Q2", 9.0, 10.0),
            _make_result("Q3", 8.5, 10.0),
        ]
        ae.evaluate(results)
        assert ae.current_difficulty == DifficultyLevel.MEDIUM

        # Window 2: continued high → upgrade to HARD
        results.append(_make_result("Q4", 9.0, 10.0))
        results.append(_make_result("Q5", 8.5, 10.0))
        results.append(_make_result("Q6", 9.5, 10.0))
        ae.evaluate(results)
        assert ae.current_difficulty == DifficultyLevel.HARD


class TestFollowUpLogic:
    """Test follow-up question generation logic."""

    def test_hard_low_score_triggers_follow_up(self):
        ae = AdaptiveEngine()
        result = _make_result("Q1", 3.0, 13.0, difficulty="hard")  # normalized ~2.3
        assert ae.should_generate_follow_up(result) is True

    def test_hard_high_score_no_follow_up(self):
        ae = AdaptiveEngine()
        result = _make_result("Q1", 10.0, 13.0, difficulty="hard")  # normalized ~7.7
        assert ae.should_generate_follow_up(result) is False

    def test_medium_low_score_no_follow_up(self):
        ae = AdaptiveEngine()
        result = _make_result("Q1", 2.0, 10.0, difficulty="medium")
        assert ae.should_generate_follow_up(result) is False

    def test_follow_up_difficulty_is_lower(self):
        ae = AdaptiveEngine(initial_difficulty=DifficultyLevel.HARD)
        follow_up_diff = ae.get_follow_up_difficulty()
        assert follow_up_diff == DifficultyLevel.MEDIUM


class TestSkipLogic:
    """Test category skip logic."""

    def test_high_score_allows_skip(self):
        ae = AdaptiveEngine()
        result = _make_result("Q1", 9.5, 10.0)  # normalized 9.5
        assert ae.should_skip_category(result) is True

    def test_moderate_score_no_skip(self):
        ae = AdaptiveEngine()
        result = _make_result("Q1", 7.0, 10.0)  # normalized 7.0
        assert ae.should_skip_category(result) is False
