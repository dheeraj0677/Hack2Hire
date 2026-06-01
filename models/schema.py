"""
Data classes for the Interview Simulation Engine.

All entities that flow through the system are defined here with
validation helpers and serialization support.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


# ──────────────────────────────────────────────
# Enums
# ──────────────────────────────────────────────

class DifficultyLevel(str, Enum):
    """Question difficulty tier."""
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"

    @classmethod
    def from_str(cls, value: str) -> "DifficultyLevel":
        """Parse a string into a DifficultyLevel, case-insensitive."""
        try:
            return cls(value.strip().lower())
        except (ValueError, AttributeError):
            raise ValueError(
                f"Invalid difficulty level '{value}'. "
                f"Must be one of: {[e.value for e in cls]}"
            )


class QuestionCategory(str, Enum):
    """Category / domain of a question."""
    TECHNICAL = "technical"
    BEHAVIORAL = "behavioral"
    SITUATIONAL = "situational"

    @classmethod
    def from_str(cls, value: str) -> "QuestionCategory":
        try:
            return cls(value.strip().lower())
        except (ValueError, AttributeError):
            raise ValueError(
                f"Invalid question category '{value}'. "
                f"Must be one of: {[e.value for e in cls]}"
            )


class InterviewState(str, Enum):
    """FSM states for the interview engine."""
    INITIALIZED = "initialized"
    VALIDATING = "validating"
    IN_PROGRESS = "in_progress"
    EVALUATING = "evaluating"
    TERMINATED = "terminated"
    COMPLETED = "completed"


class TerminationReason(str, Enum):
    """Why the interview ended."""
    COMPLETED_ALL = "completed"
    TIME_EXCEEDED = "time_exceeded"
    MAX_QUESTIONS = "max_questions_reached"
    CONSECUTIVE_FAILURES = "terminated_poor_performance"
    BELOW_THRESHOLD = "terminated_below_threshold"
    NO_RESPONSE = "terminated_no_response"
    VALIDATION_FAILED = "validation_failed"


# ──────────────────────────────────────────────
# Input Data Classes
# ──────────────────────────────────────────────

@dataclass
class CandidateProfile:
    """Candidate metadata."""
    candidate_id: str
    name: str
    experience_years: float
    skills: List[str]
    target_role: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CandidateProfile":
        return cls(
            candidate_id=str(data["candidate_id"]),
            name=str(data["name"]),
            experience_years=float(data["experience_years"]),
            skills=[str(s) for s in data.get("skills", [])],
            target_role=str(data["target_role"]),
        )


@dataclass
class JobDescription:
    """Target role requirements."""
    role: str
    required_skills: List[str]
    min_experience: float
    difficulty_preference: str = "medium"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "JobDescription":
        return cls(
            role=str(data["role"]),
            required_skills=[str(s) for s in data.get("required_skills", [])],
            min_experience=float(data.get("min_experience", 0)),
            difficulty_preference=str(data.get("difficulty_preference", "medium")),
        )


@dataclass
class InteractionEvent:
    """A single question-response pair in the interview log."""
    question_id: str
    question_text: str
    difficulty_level: DifficultyLevel
    category: QuestionCategory
    candidate_response: Optional[str]
    time_taken_seconds: float
    max_time_seconds: float = 300.0
    is_follow_up: bool = False
    timestamp: Optional[str] = None
    # Optional pre-evaluated sub-scores (each 0–10)
    relevance_score: Optional[float] = None
    depth_score: Optional[float] = None
    accuracy_score: Optional[float] = None
    clarity_score: Optional[float] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "InteractionEvent":
        return cls(
            question_id=str(data["question_id"]),
            question_text=str(data["question_text"]),
            difficulty_level=DifficultyLevel.from_str(data["difficulty_level"]),
            category=QuestionCategory.from_str(data["category"]),
            candidate_response=data.get("candidate_response"),
            time_taken_seconds=float(data["time_taken_seconds"]),
            max_time_seconds=float(data.get("max_time_seconds", 300.0)),
            is_follow_up=bool(data.get("is_follow_up", False)),
            timestamp=data.get("timestamp"),
            relevance_score=_opt_float(data.get("relevance_score")),
            depth_score=_opt_float(data.get("depth_score")),
            accuracy_score=_opt_float(data.get("accuracy_score")),
            clarity_score=_opt_float(data.get("clarity_score")),
        )

    @property
    def has_response(self) -> bool:
        """True if the candidate actually responded."""
        return (
            self.candidate_response is not None
            and self.candidate_response.strip() != ""
        )


@dataclass
class ScoringConfig:
    """Weights for per-question scoring criteria (must sum to 1.0)."""
    relevance_weight: float = 0.30
    depth_weight: float = 0.25
    accuracy_weight: float = 0.25
    clarity_weight: float = 0.10
    time_efficiency_weight: float = 0.10

    # Difficulty multipliers
    easy_multiplier: float = 0.8
    medium_multiplier: float = 1.0
    hard_multiplier: float = 1.3

    # Time efficiency thresholds (as fractions of max_time)
    fast_threshold: float = 0.30   # below → too-fast penalty
    slow_threshold: float = 0.90   # above → slow penalty
    overtime_threshold: float = 1.0 # above → overtime penalty

    fast_modifier: float = 0.85
    slow_modifier: float = 0.90
    overtime_modifier: float = 0.70
    normal_modifier: float = 1.0

    # Skill-match bonus
    skill_match_bonus: float = 0.05   # per matching skill, capped at 0.15

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "ScoringConfig":
        if data is None:
            return cls()
        return cls(**{k: float(v) for k, v in data.items() if hasattr(cls, k)})

    @property
    def weights_sum(self) -> float:
        return (
            self.relevance_weight
            + self.depth_weight
            + self.accuracy_weight
            + self.clarity_weight
            + self.time_efficiency_weight
        )

    def get_difficulty_multiplier(self, level: DifficultyLevel) -> float:
        return {
            DifficultyLevel.EASY: self.easy_multiplier,
            DifficultyLevel.MEDIUM: self.medium_multiplier,
            DifficultyLevel.HARD: self.hard_multiplier,
        }[level]


@dataclass
class TerminationConfig:
    """Thresholds that trigger early interview termination."""
    max_questions: int = 15
    max_time_seconds: float = 2700.0  # 45 minutes
    max_consecutive_failures: int = 3
    min_score_threshold: float = 3.0  # running avg below this after N questions
    min_questions_for_threshold: int = 5  # need at least N questions before threshold check

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "TerminationConfig":
        if data is None:
            return cls()
        kwargs = {}
        if "max_questions" in data:
            kwargs["max_questions"] = int(data["max_questions"])
        if "max_time_seconds" in data:
            kwargs["max_time_seconds"] = float(data["max_time_seconds"])
        if "max_consecutive_failures" in data:
            kwargs["max_consecutive_failures"] = int(data["max_consecutive_failures"])
        if "min_score_threshold" in data:
            kwargs["min_score_threshold"] = float(data["min_score_threshold"])
        if "min_questions_for_threshold" in data:
            kwargs["min_questions_for_threshold"] = int(data["min_questions_for_threshold"])
        return cls(**kwargs)


# ──────────────────────────────────────────────
# Top-Level Input
# ──────────────────────────────────────────────

@dataclass
class InterviewInput:
    """Complete input to the simulation engine."""
    candidate: CandidateProfile
    job_description: JobDescription
    interaction_events: List[InteractionEvent]
    scoring_config: ScoringConfig = field(default_factory=ScoringConfig)
    termination_config: TerminationConfig = field(default_factory=TerminationConfig)
    session_id: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "InterviewInput":
        return cls(
            candidate=CandidateProfile.from_dict(data["candidate_profile"]),
            job_description=JobDescription.from_dict(data["job_description"]),
            interaction_events=[
                InteractionEvent.from_dict(e) for e in data["interaction_events"]
            ],
            scoring_config=ScoringConfig.from_dict(data.get("scoring_config")),
            termination_config=TerminationConfig.from_dict(
                data.get("termination_config")
            ),
            session_id=data.get("session_id"),
        )


# ──────────────────────────────────────────────
# Output Data Classes
# ──────────────────────────────────────────────

@dataclass
class QuestionResult:
    """Score breakdown for one question."""
    question_id: str
    category: str
    difficulty: str
    raw_score: float        # weighted criteria score (0–10)
    difficulty_multiplier: float
    time_modifier: float
    final_score: float      # raw × difficulty × time
    max_possible: float     # 10 × difficulty multiplier
    is_follow_up: bool
    time_taken_seconds: float
    had_response: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CategoryBreakdown:
    """Aggregated scores per question category."""
    category: str
    questions_count: int
    total_score: float
    max_possible: float
    average_score: float
    percentage: float       # (total / max_possible) × 100

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AdaptiveTrace:
    """Record of a difficulty adjustment decision."""
    after_question_id: str
    window_scores: List[float]
    previous_difficulty: str
    new_difficulty: str
    reason: str


@dataclass
class InterviewOutput:
    """Complete simulation output."""
    session_id: Optional[str]
    candidate_id: str
    candidate_name: str
    target_role: str
    # Core result
    interview_readiness_score: float  # 0–100
    status: str                       # TerminationReason value
    termination_reason: str
    # Breakdown
    questions_attempted: int
    questions_answered: int
    total_time_seconds: float
    category_breakdown: List[CategoryBreakdown]
    question_results: List[QuestionResult]
    # Adaptive trace
    difficulty_adjustments: List[AdaptiveTrace]
    final_difficulty: str
    # Skill match
    skill_match_score: float  # 0–1
    matched_skills: List[str]
    # Metadata
    engine_version: str = "1.0.0"

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "session_id": self.session_id,
            "candidate_id": self.candidate_id,
            "candidate_name": self.candidate_name,
            "target_role": self.target_role,
            "interview_readiness_score": round(self.interview_readiness_score, 2),
            "status": self.status,
            "termination_reason": self.termination_reason,
            "questions_attempted": self.questions_attempted,
            "questions_answered": self.questions_answered,
            "total_time_seconds": round(self.total_time_seconds, 2),
            "category_breakdown": [c.to_dict() for c in self.category_breakdown],
            "question_results": [q.to_dict() for q in self.question_results],
            "difficulty_adjustments": [asdict(a) for a in self.difficulty_adjustments],
            "final_difficulty": self.final_difficulty,
            "skill_match_score": round(self.skill_match_score, 2),
            "matched_skills": self.matched_skills,
            "engine_version": self.engine_version,
        }
        return d


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _opt_float(value: Any) -> Optional[float]:
    """Safely convert to float or None."""
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None
