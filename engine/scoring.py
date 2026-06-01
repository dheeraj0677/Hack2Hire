"""
Scoring Engine for the Interview Simulation Engine.

Computes per-question scores and aggregates them into category breakdowns
and the final Interview Readiness Score.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from models.schema import (
    CategoryBreakdown,
    DifficultyLevel,
    InteractionEvent,
    InterviewInput,
    QuestionResult,
    ScoringConfig,
)


class ScoringEngine:
    """Computes scores for individual questions and the overall interview."""

    def __init__(self, config: ScoringConfig):
        self.config = config

    # ── Per-Question Scoring ────────────────────

    def score_question(self, event: InteractionEvent) -> QuestionResult:
        """
        Score a single interaction event.

        Scoring pipeline:
        1. Compute weighted criteria score (0–10)
        2. Apply difficulty multiplier
        3. Apply time efficiency modifier
        4. Return final score + metadata
        """
        # If no response, score is 0
        if not event.has_response:
            difficulty_mult = self.config.get_difficulty_multiplier(event.difficulty_level)
            return QuestionResult(
                question_id=event.question_id,
                category=event.category.value,
                difficulty=event.difficulty_level.value,
                raw_score=0.0,
                difficulty_multiplier=difficulty_mult,
                time_modifier=1.0,
                final_score=0.0,
                max_possible=10.0 * difficulty_mult,
                is_follow_up=event.is_follow_up,
                time_taken_seconds=event.time_taken_seconds,
                had_response=False,
            )

        # Step 1: Compute raw weighted score
        raw_score = self._compute_weighted_score(event)

        # Step 2: Difficulty multiplier
        difficulty_mult = self.config.get_difficulty_multiplier(event.difficulty_level)

        # Step 3: Time efficiency modifier
        time_modifier = self._compute_time_modifier(event)

        # Final score
        final_score = raw_score * difficulty_mult * time_modifier

        return QuestionResult(
            question_id=event.question_id,
            category=event.category.value,
            difficulty=event.difficulty_level.value,
            raw_score=round(raw_score, 4),
            difficulty_multiplier=difficulty_mult,
            time_modifier=round(time_modifier, 4),
            final_score=round(final_score, 4),
            max_possible=round(10.0 * difficulty_mult, 4),
            is_follow_up=event.is_follow_up,
            time_taken_seconds=event.time_taken_seconds,
            had_response=True,
        )

    def _compute_weighted_score(self, event: InteractionEvent) -> float:
        """
        Compute the weighted criteria score for a question (0–10).

        If individual sub-scores are provided, use them with weights.
        Otherwise, estimate from response characteristics.
        """
        cfg = self.config

        # Use provided sub-scores if available
        relevance = event.relevance_score
        depth = event.depth_score
        accuracy = event.accuracy_score
        clarity = event.clarity_score

        # If any sub-score is missing, estimate it
        if relevance is None:
            relevance = self._estimate_relevance(event)
        if depth is None:
            depth = self._estimate_depth(event)
        if accuracy is None:
            accuracy = self._estimate_accuracy(event)
        if clarity is None:
            clarity = self._estimate_clarity(event)

        # Time efficiency as a criterion score (0–10)
        time_score = self._compute_time_score(event)

        weighted = (
            relevance * cfg.relevance_weight
            + depth * cfg.depth_weight
            + accuracy * cfg.accuracy_weight
            + clarity * cfg.clarity_weight
            + time_score * cfg.time_efficiency_weight
        )

        return min(10.0, max(0.0, weighted))

    def _compute_time_modifier(self, event: InteractionEvent) -> float:
        """
        Compute a time-based modifier for the question score.

        - Too fast (< 30% of max): may indicate shallow response → 0.85
        - Normal: 1.0
        - Slow (> 90% of max): slight penalty → 0.90
        - Overtime (> 100% of max): significant penalty → 0.70
        """
        cfg = self.config
        max_time = event.max_time_seconds
        if max_time <= 0:
            return cfg.normal_modifier

        ratio = event.time_taken_seconds / max_time

        if ratio > cfg.overtime_threshold:
            return cfg.overtime_modifier
        elif ratio > cfg.slow_threshold:
            return cfg.slow_modifier
        elif ratio < cfg.fast_threshold:
            return cfg.fast_modifier
        else:
            return cfg.normal_modifier

    def _compute_time_score(self, event: InteractionEvent) -> float:
        """Time efficiency as a 0–10 score for the weighted criteria."""
        max_time = event.max_time_seconds
        if max_time <= 0:
            return 5.0

        ratio = event.time_taken_seconds / max_time

        if ratio > 1.0:
            return max(0.0, 3.0 - (ratio - 1.0) * 5)
        elif ratio > 0.9:
            return 5.0
        elif ratio < 0.3:
            return 5.0  # too fast, uncertain
        else:
            # Ideal zone: 0.3–0.9 → 7–10
            normalized = (ratio - 0.3) / 0.6
            return 7.0 + normalized * 3.0

    # ── Estimation Heuristics ───────────────────
    # These are used when sub-scores are not provided in the input.
    # They use simple response-length-based heuristics as a baseline.

    def _estimate_relevance(self, event: InteractionEvent) -> float:
        """Estimate relevance from response characteristics."""
        if not event.has_response:
            return 0.0
        response = event.candidate_response or ""
        length = len(response.strip())
        # Very short responses are likely not relevant
        if length < 20:
            return 3.0
        elif length < 50:
            return 5.0
        elif length < 200:
            return 7.0
        else:
            return 8.0

    def _estimate_depth(self, event: InteractionEvent) -> float:
        """Estimate depth from response length."""
        if not event.has_response:
            return 0.0
        response = event.candidate_response or ""
        length = len(response.strip())
        if length < 30:
            return 2.5
        elif length < 100:
            return 5.5
        elif length < 300:
            return 7.5
        else:
            return 8.5

    def _estimate_accuracy(self, event: InteractionEvent) -> float:
        """Estimate accuracy — defaults to moderate when no sub-score given."""
        if not event.has_response:
            return 0.0
        return 6.0  # conservative default

    def _estimate_clarity(self, event: InteractionEvent) -> float:
        """Estimate clarity."""
        if not event.has_response:
            return 0.0
        response = event.candidate_response or ""
        # Simple heuristic: sentence structure presence
        sentences = [s.strip() for s in response.split(".") if s.strip()]
        if len(sentences) >= 3:
            return 7.5
        elif len(sentences) >= 1:
            return 5.5
        return 3.0

    # ── Aggregation ─────────────────────────────

    def compute_skill_match(
        self, candidate_skills: List[str], required_skills: List[str]
    ) -> Tuple[float, List[str]]:
        """
        Compute skill overlap between candidate and job requirements.

        Returns:
            Tuple of (match_ratio 0–1, list of matched skills)
        """
        if not required_skills:
            return 1.0, []

        candidate_lower = {s.lower().strip() for s in candidate_skills}
        required_lower = {s.lower().strip() for s in required_skills}

        matched = candidate_lower & required_lower
        matched_original = [
            s for s in candidate_skills if s.lower().strip() in matched
        ]

        ratio = len(matched) / len(required_lower)
        return round(ratio, 4), matched_original

    def compute_category_breakdown(
        self, results: List[QuestionResult]
    ) -> List[CategoryBreakdown]:
        """
        Aggregate question results by category.

        Returns a list of CategoryBreakdown, one per unique category.
        """
        by_cat: Dict[str, List[QuestionResult]] = {}
        for r in results:
            by_cat.setdefault(r.category, []).append(r)

        breakdowns = []
        for category, cat_results in sorted(by_cat.items()):
            total = sum(r.final_score for r in cat_results)
            max_possible = sum(r.max_possible for r in cat_results)
            count = len(cat_results)
            avg = total / count if count > 0 else 0.0
            pct = (total / max_possible * 100) if max_possible > 0 else 0.0

            breakdowns.append(
                CategoryBreakdown(
                    category=category,
                    questions_count=count,
                    total_score=round(total, 2),
                    max_possible=round(max_possible, 2),
                    average_score=round(avg, 2),
                    percentage=round(pct, 2),
                )
            )

        return breakdowns

    def compute_interview_readiness_score(
        self,
        results: List[QuestionResult],
        skill_match_ratio: float,
    ) -> float:
        """
        Compute the final Interview Readiness Score (0–100).

        Formula:
            base = (total_final_score / total_max_possible) × 100
            bonus = min(skill_match_ratio × skill_match_bonus × 100, 15)
            IRS = min(100, base + bonus)
        """
        if not results:
            return 0.0

        total_score = sum(r.final_score for r in results)
        total_max = sum(r.max_possible for r in results)

        if total_max <= 0:
            return 0.0

        base = (total_score / total_max) * 100.0
        bonus = min(
            skill_match_ratio * self.config.skill_match_bonus * 100,
            15.0,
        )

        return min(100.0, round(base + bonus, 2))
