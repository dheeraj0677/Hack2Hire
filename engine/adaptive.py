"""
Adaptive Difficulty Logic for the Interview Simulation Engine.

Adjusts the effective difficulty level based on the candidate's
recent performance using a sliding window approach.
"""

from __future__ import annotations

from typing import List, Optional

from models.schema import (
    AdaptiveTrace,
    DifficultyLevel,
    QuestionResult,
)


# Ordered difficulty levels for incrementing/decrementing
_DIFFICULTY_ORDER = [DifficultyLevel.EASY, DifficultyLevel.MEDIUM, DifficultyLevel.HARD]


class AdaptiveEngine:
    """
    Manages adaptive difficulty adjustments during the interview.

    Uses a sliding window of recent question scores to decide
    whether to increase, decrease, or maintain the current difficulty.
    """

    # Thresholds
    HIGH_SCORE_THRESHOLD = 7.0   # score ≥ this counts as "high"
    LOW_SCORE_THRESHOLD = 4.0    # score < this counts as "low"
    WINDOW_SIZE = 3              # number of recent questions to consider
    UPGRADE_REQUIREMENT = 3      # N out of N high → upgrade
    DOWNGRADE_REQUIREMENT = 2    # N out of WINDOW_SIZE low → downgrade

    # Follow-up logic
    FOLLOW_UP_TRIGGER_SCORE = 5.0   # hard question below this → follow-up
    SKIP_TRIGGER_SCORE = 9.0        # any question above this → may skip

    def __init__(self, initial_difficulty: DifficultyLevel = DifficultyLevel.MEDIUM):
        self.current_difficulty = initial_difficulty
        self.adjustments: List[AdaptiveTrace] = []

    def evaluate(
        self,
        results_so_far: List[QuestionResult],
    ) -> DifficultyLevel:
        """
        Evaluate whether difficulty should change after the latest question.

        Called after each question is scored. Uses the last WINDOW_SIZE
        results to make the decision.

        Returns:
            The (possibly updated) current difficulty level.
        """
        if len(results_so_far) < self.WINDOW_SIZE:
            return self.current_difficulty

        window = results_so_far[-self.WINDOW_SIZE:]
        window_scores = [r.final_score / r.max_possible * 10 if r.max_possible > 0 else 0
                         for r in window]

        prev_difficulty = self.current_difficulty
        new_difficulty = self.current_difficulty

        high_count = sum(1 for s in window_scores if s >= self.HIGH_SCORE_THRESHOLD)
        low_count = sum(1 for s in window_scores if s < self.LOW_SCORE_THRESHOLD)

        if high_count >= self.UPGRADE_REQUIREMENT:
            new_difficulty = self._increase_difficulty(self.current_difficulty)
            reason = (
                f"All {self.WINDOW_SIZE} recent scores >= {self.HIGH_SCORE_THRESHOLD} "
                f"(scores: {[round(s, 1) for s in window_scores]})"
            )
        elif low_count >= self.DOWNGRADE_REQUIREMENT:
            new_difficulty = self._decrease_difficulty(self.current_difficulty)
            reason = (
                f"{low_count}/{self.WINDOW_SIZE} recent scores < {self.LOW_SCORE_THRESHOLD} "
                f"(scores: {[round(s, 1) for s in window_scores]})"
            )
        else:
            reason = "mixed"

        if new_difficulty != prev_difficulty:
            self.current_difficulty = new_difficulty
            self.adjustments.append(
                AdaptiveTrace(
                    after_question_id=results_so_far[-1].question_id,
                    window_scores=[round(s, 2) for s in window_scores],
                    previous_difficulty=prev_difficulty.value,
                    new_difficulty=new_difficulty.value,
                    reason=reason,
                )
            )

        return self.current_difficulty

    def should_generate_follow_up(self, result: QuestionResult) -> bool:
        """
        Determine if a follow-up question should be generated.

        Rules:
        - Hard question with score < FOLLOW_UP_TRIGGER_SCORE → follow-up at medium
        """
        if result.difficulty == DifficultyLevel.HARD.value:
            normalized = (result.final_score / result.max_possible * 10) if result.max_possible > 0 else 0
            return normalized < self.FOLLOW_UP_TRIGGER_SCORE
        return False

    def should_skip_category(self, result: QuestionResult) -> bool:
        """
        Determine if the candidate can skip ahead to the next category.

        Rules:
        - Any question with normalized score ≥ SKIP_TRIGGER_SCORE → may skip
        """
        normalized = (result.final_score / result.max_possible * 10) if result.max_possible > 0 else 0
        return normalized >= self.SKIP_TRIGGER_SCORE

    def get_follow_up_difficulty(self) -> DifficultyLevel:
        """The difficulty level to use for a follow-up question."""
        return self._decrease_difficulty(self.current_difficulty)

    # ── Helpers ──────────────────────────────────

    @staticmethod
    def _increase_difficulty(current: DifficultyLevel) -> DifficultyLevel:
        """Move to the next higher difficulty, capped at HARD."""
        idx = _DIFFICULTY_ORDER.index(current)
        return _DIFFICULTY_ORDER[min(idx + 1, len(_DIFFICULTY_ORDER) - 1)]

    @staticmethod
    def _decrease_difficulty(current: DifficultyLevel) -> DifficultyLevel:
        """Move to the next lower difficulty, capped at EASY."""
        idx = _DIFFICULTY_ORDER.index(current)
        return _DIFFICULTY_ORDER[max(idx - 1, 0)]
