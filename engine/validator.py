"""
Input Validator for the Interview Simulation Engine.

Validates the raw JSON dictionary before it enters the engine.
Returns a list of structured error messages if validation fails.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from models.schema import DifficultyLevel, QuestionCategory


class ValidationError:
    """Structured validation error."""

    def __init__(self, field: str, message: str, severity: str = "error"):
        self.field = field
        self.message = message
        self.severity = severity  # "error" or "warning"

    def __repr__(self) -> str:
        return f"[{self.severity.upper()}] {self.field}: {self.message}"

    def to_dict(self) -> Dict[str, str]:
        return {
            "field": self.field,
            "message": self.message,
            "severity": self.severity,
        }


class InputValidator:
    """Validates raw interview input data."""

    REQUIRED_TOP_LEVEL = ["candidate_profile", "job_description", "interaction_events"]
    REQUIRED_CANDIDATE = ["candidate_id", "name", "experience_years", "skills", "target_role"]
    REQUIRED_JOB = ["role", "required_skills"]
    REQUIRED_EVENT = [
        "question_id",
        "question_text",
        "difficulty_level",
        "category",
        "time_taken_seconds",
    ]

    def __init__(self):
        self.errors: List[ValidationError] = []
        self.warnings: List[ValidationError] = []

    def validate(self, data: Any) -> Tuple[bool, List[ValidationError]]:
        """
        Validate the input data.

        Returns:
            Tuple of (is_valid, list_of_errors_and_warnings)
        """
        self.errors = []
        self.warnings = []

        # Must be a dictionary
        if not isinstance(data, dict):
            self.errors.append(
                ValidationError("root", "Input must be a JSON object (dictionary)")
            )
            return False, self.errors

        # Top-level required fields
        self._check_required_fields(data, self.REQUIRED_TOP_LEVEL, "root")
        if self.errors:
            return False, self.errors

        # Validate each section
        self._validate_candidate(data.get("candidate_profile", {}))
        self._validate_job_description(data.get("job_description", {}))
        self._validate_events(data.get("interaction_events", []))
        self._validate_scoring_config(data.get("scoring_config"))
        self._validate_termination_config(data.get("termination_config"))

        all_issues = self.errors + self.warnings
        return len(self.errors) == 0, all_issues

    # ── Section Validators ──────────────────────

    def _validate_candidate(self, candidate: Any) -> None:
        """Validate candidate_profile section."""
        if not isinstance(candidate, dict):
            self.errors.append(
                ValidationError("candidate_profile", "Must be a JSON object")
            )
            return

        self._check_required_fields(candidate, self.REQUIRED_CANDIDATE, "candidate_profile")

        # Type checks
        if "experience_years" in candidate:
            try:
                exp = float(candidate["experience_years"])
                if exp < 0:
                    self.errors.append(
                        ValidationError(
                            "candidate_profile.experience_years",
                            "Must be non-negative",
                        )
                    )
            except (ValueError, TypeError):
                self.errors.append(
                    ValidationError(
                        "candidate_profile.experience_years",
                        "Must be a number",
                    )
                )

        if "skills" in candidate and not isinstance(candidate["skills"], list):
            self.errors.append(
                ValidationError("candidate_profile.skills", "Must be a list")
            )

    def _validate_job_description(self, jd: Any) -> None:
        """Validate job_description section."""
        if not isinstance(jd, dict):
            self.errors.append(
                ValidationError("job_description", "Must be a JSON object")
            )
            return

        self._check_required_fields(jd, self.REQUIRED_JOB, "job_description")

        if "required_skills" in jd and not isinstance(jd["required_skills"], list):
            self.errors.append(
                ValidationError("job_description.required_skills", "Must be a list")
            )

        if "min_experience" in jd:
            try:
                val = float(jd["min_experience"])
                if val < 0:
                    self.errors.append(
                        ValidationError(
                            "job_description.min_experience",
                            "Must be non-negative",
                        )
                    )
            except (ValueError, TypeError):
                self.errors.append(
                    ValidationError(
                        "job_description.min_experience",
                        "Must be a number",
                    )
                )

    def _validate_events(self, events: Any) -> None:
        """Validate interaction_events array."""
        if not isinstance(events, list):
            self.errors.append(
                ValidationError("interaction_events", "Must be a list")
            )
            return

        if len(events) == 0:
            self.errors.append(
                ValidationError(
                    "interaction_events",
                    "Must contain at least one event",
                )
            )
            return

        seen_ids: set = set()
        prev_timestamp: Optional[datetime] = None

        for i, event in enumerate(events):
            path = f"interaction_events[{i}]"

            if not isinstance(event, dict):
                self.errors.append(ValidationError(path, "Each event must be a JSON object"))
                continue

            self._check_required_fields(event, self.REQUIRED_EVENT, path)

            # Unique question IDs
            qid = event.get("question_id")
            if qid is not None:
                if qid in seen_ids:
                    self.errors.append(
                        ValidationError(f"{path}.question_id", f"Duplicate question_id '{qid}'")
                    )
                seen_ids.add(qid)

            # Difficulty level
            dl = event.get("difficulty_level")
            if dl is not None:
                try:
                    DifficultyLevel.from_str(dl)
                except ValueError as e:
                    self.errors.append(ValidationError(f"{path}.difficulty_level", str(e)))

            # Category
            cat = event.get("category")
            if cat is not None:
                try:
                    QuestionCategory.from_str(cat)
                except ValueError as e:
                    self.errors.append(ValidationError(f"{path}.category", str(e)))

            # time_taken_seconds
            tts = event.get("time_taken_seconds")
            if tts is not None:
                try:
                    val = float(tts)
                    if val < 0:
                        self.errors.append(
                            ValidationError(f"{path}.time_taken_seconds", "Must be non-negative")
                        )
                except (ValueError, TypeError):
                    self.errors.append(
                        ValidationError(f"{path}.time_taken_seconds", "Must be a number")
                    )

            # max_time_seconds
            mts = event.get("max_time_seconds")
            if mts is not None:
                try:
                    val = float(mts)
                    if val <= 0:
                        self.errors.append(
                            ValidationError(f"{path}.max_time_seconds", "Must be positive")
                        )
                except (ValueError, TypeError):
                    self.errors.append(
                        ValidationError(f"{path}.max_time_seconds", "Must be a number")
                    )

            # Timestamp chronology
            ts = event.get("timestamp")
            if ts is not None:
                try:
                    current_ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    if prev_timestamp is not None and current_ts < prev_timestamp:
                        self.warnings.append(
                            ValidationError(
                                f"{path}.timestamp",
                                "Timestamp is earlier than the previous event",
                                severity="warning",
                            )
                        )
                    prev_timestamp = current_ts
                except (ValueError, TypeError):
                    self.warnings.append(
                        ValidationError(
                            f"{path}.timestamp",
                            "Invalid ISO 8601 timestamp format",
                            severity="warning",
                        )
                    )

            # Score fields (optional, 0–10)
            for score_field in [
                "relevance_score",
                "depth_score",
                "accuracy_score",
                "clarity_score",
            ]:
                sv = event.get(score_field)
                if sv is not None:
                    try:
                        val = float(sv)
                        if val < 0 or val > 10:
                            self.errors.append(
                                ValidationError(
                                    f"{path}.{score_field}",
                                    "Must be between 0 and 10",
                                )
                            )
                    except (ValueError, TypeError):
                        self.errors.append(
                            ValidationError(f"{path}.{score_field}", "Must be a number")
                        )

    def _validate_scoring_config(self, config: Any) -> None:
        """Validate scoring_config if provided."""
        if config is None:
            return  # optional section, defaults will be used

        if not isinstance(config, dict):
            self.errors.append(
                ValidationError("scoring_config", "Must be a JSON object")
            )
            return

        # Weights should sum to ~1.0
        weight_fields = [
            "relevance_weight",
            "depth_weight",
            "accuracy_weight",
            "clarity_weight",
            "time_efficiency_weight",
        ]
        total = 0.0
        for wf in weight_fields:
            if wf in config:
                try:
                    val = float(config[wf])
                    if val < 0 or val > 1:
                        self.errors.append(
                            ValidationError(
                                f"scoring_config.{wf}",
                                "Weight must be between 0 and 1",
                            )
                        )
                    total += val
                except (ValueError, TypeError):
                    self.errors.append(
                        ValidationError(f"scoring_config.{wf}", "Must be a number")
                    )

        if total > 0 and abs(total - 1.0) > 0.01:
            self.warnings.append(
                ValidationError(
                    "scoring_config",
                    f"Weights sum to {total:.3f}, expected ~1.0",
                    severity="warning",
                )
            )

    def _validate_termination_config(self, config: Any) -> None:
        """Validate termination_config if provided."""
        if config is None:
            return

        if not isinstance(config, dict):
            self.errors.append(
                ValidationError("termination_config", "Must be a JSON object")
            )
            return

        int_fields = {"max_questions": 1, "max_consecutive_failures": 1, "min_questions_for_threshold": 1}
        for f, min_val in int_fields.items():
            if f in config:
                try:
                    val = int(config[f])
                    if val < min_val:
                        self.errors.append(
                            ValidationError(
                                f"termination_config.{f}",
                                f"Must be >= {min_val}",
                            )
                        )
                except (ValueError, TypeError):
                    self.errors.append(
                        ValidationError(f"termination_config.{f}", "Must be an integer")
                    )

        float_fields = {"max_time_seconds": 0, "min_score_threshold": 0}
        for f, min_val in float_fields.items():
            if f in config:
                try:
                    val = float(config[f])
                    if val < min_val:
                        self.errors.append(
                            ValidationError(
                                f"termination_config.{f}",
                                f"Must be >= {min_val}",
                            )
                        )
                except (ValueError, TypeError):
                    self.errors.append(
                        ValidationError(f"termination_config.{f}", "Must be a number")
                    )

    # ── Helpers ──────────────────────────────────

    def _check_required_fields(
        self, data: Dict[str, Any], required: List[str], context: str
    ) -> None:
        """Check that all required fields are present in data."""
        for field_name in required:
            if field_name not in data:
                self.errors.append(
                    ValidationError(
                        f"{context}.{field_name}" if context != "root" else field_name,
                        "Required field is missing",
                    )
                )
