"""Unit tests for the Termination Checker."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from models.schema import (
    DifficultyLevel,
    InteractionEvent,
    QuestionCategory,
    QuestionResult,
    TerminationConfig,
    TerminationReason,
)
from engine.termination import TerminationChecker


def _make_event(
    qid="Q1",
    response="Valid answer",
    time_taken=60,
    max_time=300,
):
    return InteractionEvent(
        question_id=qid,
        question_text="Test question",
        difficulty_level=DifficultyLevel.MEDIUM,
        category=QuestionCategory.TECHNICAL,
        candidate_response=response,
        time_taken_seconds=time_taken,
        max_time_seconds=max_time,
    )


def _make_result(
    qid="Q1",
    final_score=7.0,
    max_possible=10.0,
    had_response=True,
):
    return QuestionResult(
        question_id=qid,
        category="technical",
        difficulty="medium",
        raw_score=final_score,
        difficulty_multiplier=1.0,
        time_modifier=1.0,
        final_score=final_score,
        max_possible=max_possible,
        is_follow_up=False,
        time_taken_seconds=60,
        had_response=had_response,
    )


class TestNoResponseTermination:
    """Test Priority 1: No response termination."""

    def test_empty_response_terminates(self):
        tc = TerminationChecker(TerminationConfig())
        event = _make_event(response="")
        result = _make_result(had_response=False, final_score=0)
        reason = tc.check(event, result, [result])
        assert reason == TerminationReason.NO_RESPONSE

    def test_none_response_terminates(self):
        tc = TerminationChecker(TerminationConfig())
        event = _make_event(response=None)
        result = _make_result(had_response=False, final_score=0)
        reason = tc.check(event, result, [result])
        assert reason == TerminationReason.NO_RESPONSE

    def test_whitespace_response_terminates(self):
        tc = TerminationChecker(TerminationConfig())
        event = _make_event(response="   ")
        result = _make_result(had_response=False, final_score=0)
        reason = tc.check(event, result, [result])
        assert reason == TerminationReason.NO_RESPONSE


class TestTimeTermination:
    """Test Priority 2: Time limit termination."""

    def test_time_exceeded_terminates(self):
        config = TerminationConfig(max_time_seconds=100)
        tc = TerminationChecker(config)
        event = _make_event(time_taken=110)
        result = _make_result()
        reason = tc.check(event, result, [result])
        assert reason == TerminationReason.TIME_EXCEEDED

    def test_cumulative_time_exceeded(self):
        config = TerminationConfig(max_time_seconds=100)
        tc = TerminationChecker(config)

        # Q1: 60s
        e1 = _make_event(qid="Q1", time_taken=60)
        r1 = _make_result(qid="Q1")
        reason = tc.check(e1, r1, [r1])
        assert reason is None

        # Q2: 50s → total 110s > 100s
        e2 = _make_event(qid="Q2", time_taken=50)
        r2 = _make_result(qid="Q2")
        reason = tc.check(e2, r2, [r1, r2])
        assert reason == TerminationReason.TIME_EXCEEDED

    def test_just_under_time_limit(self):
        config = TerminationConfig(max_time_seconds=100)
        tc = TerminationChecker(config)
        event = _make_event(time_taken=99)
        result = _make_result()
        reason = tc.check(event, result, [result])
        assert reason is None


class TestConsecutiveFailures:
    """Test Priority 3: Consecutive failures termination."""

    def test_three_consecutive_failures_terminates(self):
        config = TerminationConfig(max_consecutive_failures=3, max_time_seconds=99999)
        tc = TerminationChecker(config)
        all_results = []

        for i in range(3):
            event = _make_event(qid=f"Q{i}", time_taken=60)
            result = _make_result(qid=f"Q{i}", final_score=1.0)  # normalized 1.0 < 4.0
            all_results.append(result)
            reason = tc.check(event, result, all_results)

        assert reason == TerminationReason.CONSECUTIVE_FAILURES

    def test_good_answer_resets_failures(self):
        config = TerminationConfig(max_consecutive_failures=3, max_time_seconds=99999)
        tc = TerminationChecker(config)
        all_results = []

        # Two bad answers
        for i in range(2):
            event = _make_event(qid=f"Q{i}", time_taken=60)
            result = _make_result(qid=f"Q{i}", final_score=1.0)
            all_results.append(result)
            tc.check(event, result, all_results)

        # One good answer resets
        event = _make_event(qid="Q2", time_taken=60)
        result = _make_result(qid="Q2", final_score=7.0)
        all_results.append(result)
        reason = tc.check(event, result, all_results)
        assert reason is None
        assert tc.consecutive_failures == 0


class TestScoreFloor:
    """Test Priority 4: Score floor termination."""

    def test_below_threshold_after_min_questions(self):
        config = TerminationConfig(
            min_score_threshold=3.0,
            min_questions_for_threshold=3,
            max_time_seconds=99999,
            max_consecutive_failures=99,
        )
        tc = TerminationChecker(config)
        all_results = []

        for i in range(3):
            event = _make_event(qid=f"Q{i}", time_taken=60)
            result = _make_result(qid=f"Q{i}", final_score=2.0)  # avg normalized = 2.0 < 3.0
            all_results.append(result)
            reason = tc.check(event, result, all_results)

        assert reason == TerminationReason.BELOW_THRESHOLD

    def test_no_threshold_check_before_min_questions(self):
        config = TerminationConfig(
            min_score_threshold=3.0,
            min_questions_for_threshold=5,
            max_time_seconds=99999,
            max_consecutive_failures=99,
        )
        tc = TerminationChecker(config)
        all_results = []

        for i in range(3):
            event = _make_event(qid=f"Q{i}", time_taken=60)
            result = _make_result(qid=f"Q{i}", final_score=1.0)
            all_results.append(result)
            reason = tc.check(event, result, all_results)

        assert reason is None  # only 3 questions, threshold needs 5


class TestMaxQuestions:
    """Test Priority 5: Max questions termination."""

    def test_max_questions_terminates(self):
        config = TerminationConfig(
            max_questions=3,
            max_time_seconds=99999,
            max_consecutive_failures=99,
            min_questions_for_threshold=99,
        )
        tc = TerminationChecker(config)
        all_results = []

        for i in range(3):
            event = _make_event(qid=f"Q{i}", time_taken=60)
            result = _make_result(qid=f"Q{i}")
            all_results.append(result)
            reason = tc.check(event, result, all_results)

        assert reason == TerminationReason.MAX_QUESTIONS


class TestTerminationPriority:
    """Test that higher-priority conditions take precedence."""

    def test_no_response_beats_time_exceeded(self):
        config = TerminationConfig(max_time_seconds=10)
        tc = TerminationChecker(config)
        # Both no response AND time exceeded
        event = _make_event(response="", time_taken=20)
        result = _make_result(had_response=False, final_score=0)
        reason = tc.check(event, result, [result])
        # No response has higher priority
        assert reason == TerminationReason.NO_RESPONSE


class TestStateTracking:
    """Test internal state tracking."""

    def test_state_tracks_questions_and_time(self):
        tc = TerminationChecker(TerminationConfig(max_time_seconds=99999, max_questions=99))
        event = _make_event(time_taken=120)
        result = _make_result()
        tc.check(event, result, [result])

        state = tc.get_state()
        assert state["question_count"] == 1
        assert state["total_time"] == 120.0
