"""Edge case and stress tests for the Interview Simulation Engine."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from engine.state_machine import InterviewEngine
from engine.validator import InputValidator
from models.schema import TerminationReason


class TestValidatorEdgeCases:
    """Test input validator with tricky inputs."""

    def test_duplicate_question_ids_rejected(self):
        validator = InputValidator()
        data = {
            "candidate_profile": {
                "candidate_id": "C1", "name": "Test", "experience_years": 1,
                "skills": [], "target_role": "Dev",
            },
            "job_description": {"role": "Dev", "required_skills": []},
            "interaction_events": [
                {
                    "question_id": "Q1", "question_text": "Q?",
                    "difficulty_level": "easy", "category": "technical",
                    "time_taken_seconds": 30, "candidate_response": "Yes",
                },
                {
                    "question_id": "Q1", "question_text": "Same ID!",
                    "difficulty_level": "easy", "category": "technical",
                    "time_taken_seconds": 30, "candidate_response": "Yes",
                },
            ],
        }
        is_valid, errors = validator.validate(data)
        assert not is_valid
        error_fields = [e.field for e in errors if e.severity == "error"]
        assert any("question_id" in f for f in error_fields)

    def test_negative_experience_rejected(self):
        validator = InputValidator()
        data = {
            "candidate_profile": {
                "candidate_id": "C1", "name": "Test", "experience_years": -2,
                "skills": [], "target_role": "Dev",
            },
            "job_description": {"role": "Dev", "required_skills": []},
            "interaction_events": [
                {
                    "question_id": "Q1", "question_text": "Q?",
                    "difficulty_level": "easy", "category": "technical",
                    "time_taken_seconds": 30, "candidate_response": "Yes",
                },
            ],
        }
        is_valid, errors = validator.validate(data)
        assert not is_valid

    def test_invalid_difficulty_level_rejected(self):
        validator = InputValidator()
        data = {
            "candidate_profile": {
                "candidate_id": "C1", "name": "Test", "experience_years": 1,
                "skills": [], "target_role": "Dev",
            },
            "job_description": {"role": "Dev", "required_skills": []},
            "interaction_events": [
                {
                    "question_id": "Q1", "question_text": "Q?",
                    "difficulty_level": "impossible",
                    "category": "technical",
                    "time_taken_seconds": 30, "candidate_response": "Yes",
                },
            ],
        }
        is_valid, errors = validator.validate(data)
        assert not is_valid

    def test_negative_time_rejected(self):
        validator = InputValidator()
        data = {
            "candidate_profile": {
                "candidate_id": "C1", "name": "Test", "experience_years": 1,
                "skills": [], "target_role": "Dev",
            },
            "job_description": {"role": "Dev", "required_skills": []},
            "interaction_events": [
                {
                    "question_id": "Q1", "question_text": "Q?",
                    "difficulty_level": "easy", "category": "technical",
                    "time_taken_seconds": -5, "candidate_response": "Yes",
                },
            ],
        }
        is_valid, errors = validator.validate(data)
        assert not is_valid

    def test_score_out_of_range_rejected(self):
        validator = InputValidator()
        data = {
            "candidate_profile": {
                "candidate_id": "C1", "name": "Test", "experience_years": 1,
                "skills": [], "target_role": "Dev",
            },
            "job_description": {"role": "Dev", "required_skills": []},
            "interaction_events": [
                {
                    "question_id": "Q1", "question_text": "Q?",
                    "difficulty_level": "easy", "category": "technical",
                    "time_taken_seconds": 30, "candidate_response": "Yes",
                    "relevance_score": 15.0,
                },
            ],
        }
        is_valid, errors = validator.validate(data)
        assert not is_valid

    def test_non_chronological_timestamps_warn(self):
        validator = InputValidator()
        data = {
            "candidate_profile": {
                "candidate_id": "C1", "name": "Test", "experience_years": 1,
                "skills": [], "target_role": "Dev",
            },
            "job_description": {"role": "Dev", "required_skills": []},
            "interaction_events": [
                {
                    "question_id": "Q1", "question_text": "Q?",
                    "difficulty_level": "easy", "category": "technical",
                    "time_taken_seconds": 30, "candidate_response": "Yes",
                    "timestamp": "2026-06-01T10:00:00Z",
                },
                {
                    "question_id": "Q2", "question_text": "Q?",
                    "difficulty_level": "easy", "category": "technical",
                    "time_taken_seconds": 30, "candidate_response": "Yes",
                    "timestamp": "2026-06-01T09:00:00Z",
                },
            ],
        }
        is_valid, issues = validator.validate(data)
        assert is_valid  # timestamps are warnings, not errors
        warnings = [i for i in issues if i.severity == "warning"]
        assert len(warnings) > 0

    def test_weights_not_summing_to_one_warns(self):
        validator = InputValidator()
        data = {
            "candidate_profile": {
                "candidate_id": "C1", "name": "Test", "experience_years": 1,
                "skills": [], "target_role": "Dev",
            },
            "job_description": {"role": "Dev", "required_skills": []},
            "interaction_events": [
                {
                    "question_id": "Q1", "question_text": "Q?",
                    "difficulty_level": "easy", "category": "technical",
                    "time_taken_seconds": 30, "candidate_response": "Yes",
                },
            ],
            "scoring_config": {
                "relevance_weight": 0.5,
                "completeness_weight": 0.5,
                "accuracy_weight": 0.5,
                "communication_weight": 0.5,
                "time_efficiency_weight": 0.5,
            },
        }
        is_valid, issues = validator.validate(data)
        assert is_valid  # weights are a warning
        warnings = [i for i in issues if i.severity == "warning"]
        assert any("sum" in w.message.lower() for w in warnings)


class TestEngineEdgeCases:
    """Test engine behavior with unusual but valid inputs."""

    def test_single_question_interview(self):
        engine = InterviewEngine(verbose=False)
        data = {
            "candidate_profile": {
                "candidate_id": "C1", "name": "Solo", "experience_years": 1,
                "skills": ["Python"], "target_role": "Dev",
            },
            "job_description": {"role": "Dev", "required_skills": ["Python"]},
            "interaction_events": [
                {
                    "question_id": "Q1", "question_text": "Hello?",
                    "difficulty_level": "easy", "category": "technical",
                    "time_taken_seconds": 60, "max_time_seconds": 180,
                    "candidate_response": "Hello world. This is my response to the question with enough detail.",
                    "relevance_score": 7.0, "completeness_score": 7.0,
                    "accuracy_score": 7.0, "communication_score": 7.0,
                },
            ],
        }
        output = engine.run(data)
        assert output.status == TerminationReason.COMPLETED_ALL.value
        assert output.questions_attempted == 1
        assert output.interview_readiness_score > 0

    def test_all_same_difficulty(self):
        engine = InterviewEngine(verbose=False)
        events = []
        for i in range(5):
            events.append({
                "question_id": f"Q{i}",
                "question_text": f"Question {i}",
                "difficulty_level": "hard",
                "category": "technical",
                "time_taken_seconds": 200,
                "max_time_seconds": 360,
                "candidate_response": f"Detailed answer for question {i} with technical depth and clarity.",
                "relevance_score": 8.0, "completeness_score": 8.0,
                "accuracy_score": 8.0, "communication_score": 8.0,
            })

        data = {
            "candidate_profile": {
                "candidate_id": "C2", "name": "Hard Mode", "experience_years": 5,
                "skills": ["Everything"], "target_role": "Lead",
            },
            "job_description": {"role": "Lead", "required_skills": ["Everything"]},
            "interaction_events": events,
        }
        output = engine.run(data)
        assert output.status == TerminationReason.COMPLETED_ALL.value
        assert all(qr.difficulty == "hard" for qr in output.question_results)

    def test_termination_on_last_question(self):
        """Interview hits max_questions exactly on the last event."""
        engine = InterviewEngine(verbose=False)
        events = []
        for i in range(3):
            events.append({
                "question_id": f"Q{i}",
                "question_text": f"Question {i}",
                "difficulty_level": "medium",
                "category": "technical",
                "time_taken_seconds": 100,
                "max_time_seconds": 300,
                "candidate_response": "Solid answer with detail.",
                "relevance_score": 7.0, "completeness_score": 7.0,
                "accuracy_score": 7.0, "communication_score": 7.0,
            })

        data = {
            "candidate_profile": {
                "candidate_id": "C3", "name": "Edge Case", "experience_years": 2,
                "skills": [], "target_role": "Dev",
            },
            "job_description": {"role": "Dev", "required_skills": []},
            "termination_config": {"max_questions": 3},
            "interaction_events": events,
        }
        output = engine.run(data)
        assert output.status == TerminationReason.MAX_QUESTIONS.value
        assert output.questions_attempted == 3

    def test_all_categories_represented(self):
        engine = InterviewEngine(verbose=False)
        events = []
        for i, cat in enumerate(["technical", "behavioral", "situational"]):
            events.append({
                "question_id": f"Q{i}",
                "question_text": f"Question about {cat}",
                "difficulty_level": "medium",
                "category": cat,
                "time_taken_seconds": 120,
                "max_time_seconds": 300,
                "candidate_response": f"Good answer for {cat} question with specifics.",
                "relevance_score": 7.5, "completeness_score": 7.0,
                "accuracy_score": 7.5, "communication_score": 7.0,
            })

        data = {
            "candidate_profile": {
                "candidate_id": "C4", "name": "All Cats", "experience_years": 3,
                "skills": [], "target_role": "Dev",
            },
            "job_description": {"role": "Dev", "required_skills": []},
            "interaction_events": events,
        }
        output = engine.run(data)
        cats = {cb.category for cb in output.category_breakdown}
        assert cats == {"technical", "behavioral", "situational"}

    def test_zero_time_question(self):
        """A question with 0 seconds time taken."""
        engine = InterviewEngine(verbose=False)
        data = {
            "candidate_profile": {
                "candidate_id": "C5", "name": "Instant", "experience_years": 1,
                "skills": [], "target_role": "Dev",
            },
            "job_description": {"role": "Dev", "required_skills": []},
            "interaction_events": [
                {
                    "question_id": "Q1", "question_text": "What is 1+1?",
                    "difficulty_level": "easy", "category": "technical",
                    "time_taken_seconds": 0, "max_time_seconds": 180,
                    "candidate_response": "Two.",
                    "relevance_score": 5.0, "completeness_score": 3.0,
                    "accuracy_score": 10.0, "communication_score": 5.0,
                },
            ],
        }
        output = engine.run(data)
        assert output.status == TerminationReason.COMPLETED_ALL.value
        # Should apply fast penalty (0% < 30%)
        assert output.question_results[0].time_modifier == 0.85

    def test_verbose_mode_runs(self):
        """Ensure verbose mode doesn't crash."""
        engine = InterviewEngine(verbose=True)
        data = {
            "candidate_profile": {
                "candidate_id": "C6", "name": "Verbose", "experience_years": 1,
                "skills": [], "target_role": "Dev",
            },
            "job_description": {"role": "Dev", "required_skills": []},
            "interaction_events": [
                {
                    "question_id": "Q1", "question_text": "Test",
                    "difficulty_level": "easy", "category": "technical",
                    "time_taken_seconds": 60, "max_time_seconds": 180,
                    "candidate_response": "Answer.",
                    "relevance_score": 5.0, "completeness_score": 5.0,
                    "accuracy_score": 5.0, "communication_score": 5.0,
                },
            ],
        }
        output = engine.run(data)
        assert output.interview_readiness_score >= 0
