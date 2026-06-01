"""
Termination Rules for the Interview Simulation Engine.

Checks exit conditions after each question to determine if
the interview should end early.
"""

from __future__ import annotations

from typing import List, Optional

from models.schema import (
    InteractionEvent,
    QuestionResult,
    TerminationConfig,
    TerminationReason,
)


class TerminationChecker:
    """
    Evaluates termination conditions after each processed event.

    Checks are evaluated in priority order:
    1. No Response (highest priority)
    2. Time Exceeded
    3. Consecutive Failures
    4. Score Floor
    5. Max Questions (lowest priority)
    """

    def __init__(self, config: TerminationConfig):
        self.config = config
        self.consecutive_failures: int = 0
        self.total_time: float = 0.0
        self.question_count: int = 0

    def check(
        self,
        event: InteractionEvent,
        result: QuestionResult,
        all_results: List[QuestionResult],
    ) -> Optional[TerminationReason]:
        """
        Check all termination conditions after processing an event.

        Updates internal state (consecutive failures, time, count) and
        returns the reason for termination, or None if the interview continues.
        """
        # Update running state
        self.question_count += 1
        self.total_time += event.time_taken_seconds

        # Track consecutive failures
        if not result.had_response:
            self.consecutive_failures += 1
        else:
            # A "failure" is a normalized score below 4.0/10
            normalized = (
                (result.final_score / result.max_possible * 10)
                if result.max_possible > 0
                else 0
            )
            if normalized < 4.0:
                self.consecutive_failures += 1
            else:
                self.consecutive_failures = 0

        # ── Priority 1: No Response ─────────────
        if not event.has_response:
            return TerminationReason.NO_RESPONSE

        # ── Priority 2: Time Exceeded ───────────
        if self.total_time >= self.config.max_time_seconds:
            return TerminationReason.TIME_EXCEEDED

        # ── Priority 3: Consecutive Failures ────
        if self.consecutive_failures >= self.config.max_consecutive_failures:
            return TerminationReason.CONSECUTIVE_FAILURES

        # ── Priority 4: Score Floor ─────────────
        if self.question_count >= self.config.min_questions_for_threshold:
            running_avg = self._compute_running_average(all_results)
            if running_avg < self.config.min_score_threshold:
                return TerminationReason.BELOW_THRESHOLD

        # ── Priority 5: Max Questions ───────────
        if self.question_count >= self.config.max_questions:
            return TerminationReason.MAX_QUESTIONS

        return None

    def _compute_running_average(self, results: List[QuestionResult]) -> float:
        """
        Compute the running average of normalized scores (0–10 scale).
        """
        if not results:
            return 0.0
        total = 0.0
        for r in results:
            if r.max_possible > 0:
                total += (r.final_score / r.max_possible) * 10
            else:
                total += 0.0
        return total / len(results)

    def get_state(self) -> dict:
        """Return current checker state for debugging."""
        return {
            "question_count": self.question_count,
            "total_time": round(self.total_time, 2),
            "consecutive_failures": self.consecutive_failures,
        }
