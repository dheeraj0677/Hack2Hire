"""Integration tests for the full Interview Engine pipeline."""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from engine.state_machine import InterviewEngine
from models.schema import TerminationReason


SAMPLES_DIR = Path(__file__).resolve().parent.parent / "samples"


def _load_sample(name: str) -> dict:
    with open(SAMPLES_DIR / name, "r", encoding="utf-8") as f:
        return json.load(f)


class TestNormalFlow:
    """Test normal interview completion."""

    def test_sample_input_completes(self):
        data = _load_sample("sample_input.json")
        engine = InterviewEngine(verbose=False)
        output = engine.run(data)

        assert output.status == TerminationReason.COMPLETED_ALL.value
        assert output.interview_readiness_score > 0
        assert output.interview_readiness_score <= 100
        assert output.questions_attempted == 8
        assert output.questions_answered == 8
        assert output.candidate_name == "Priya Sharma"

    def test_output_has_all_required_fields(self):
        data = _load_sample("sample_input.json")
        engine = InterviewEngine(verbose=False)
        output = engine.run(data)
        d = output.to_dict()

        required_keys = [
            "session_id",
            "candidate_id",
            "candidate_name",
            "target_role",
            "interview_readiness_score",
            "status",
            "termination_reason",
            "questions_attempted",
            "questions_answered",
            "total_time_seconds",
            "category_breakdown",
            "question_results",
            "difficulty_adjustments",
            "final_difficulty",
            "skill_match_score",
            "matched_skills",
            "engine_version",
        ]
        for key in required_keys:
            assert key in d, f"Missing key: {key}"

    def test_category_breakdown_present(self):
        data = _load_sample("sample_input.json")
        engine = InterviewEngine(verbose=False)
        output = engine.run(data)

        assert len(output.category_breakdown) > 0
        categories = {cb.category for cb in output.category_breakdown}
        assert "technical" in categories

    def test_skill_match_computed(self):
        data = _load_sample("sample_input.json")
        engine = InterviewEngine(verbose=False)
        output = engine.run(data)

        # Priya has Python, System Design, SQL matching; Docker missing
        assert output.skill_match_score > 0
        assert output.skill_match_score < 1.0  # not full match
        assert len(output.matched_skills) >= 3

    def test_question_results_match_events(self):
        data = _load_sample("sample_input.json")
        engine = InterviewEngine(verbose=False)
        output = engine.run(data)

        assert len(output.question_results) == len(data["interaction_events"])
        for qr in output.question_results:
            assert qr.final_score >= 0
            assert qr.max_possible > 0


class TestEdgeCases:
    """Test edge case sample files."""

    def test_fast_answers_apply_time_penalty(self):
        data = _load_sample("edge_fast_answers.json")
        engine = InterviewEngine(verbose=False)
        output = engine.run(data)

        # All answers are too fast (<30% of max_time)
        for qr in output.question_results:
            if qr.had_response:
                assert qr.time_modifier == 0.85, f"{qr.question_id} should have fast penalty"

    def test_timeout_terminates(self):
        data = _load_sample("edge_timeout.json")
        engine = InterviewEngine(verbose=False)
        output = engine.run(data)

        # Total time: 250 + 280 + 350 = 880s > 600s
        assert output.status == TerminationReason.TIME_EXCEEDED.value

    def test_failure_cascade_terminates(self):
        data = _load_sample("edge_failures.json")
        engine = InterviewEngine(verbose=False)
        output = engine.run(data)

        # Should terminate due to either no_response or consecutive failures
        assert output.status in [
            TerminationReason.NO_RESPONSE.value,
            TerminationReason.CONSECUTIVE_FAILURES.value,
            TerminationReason.BELOW_THRESHOLD.value,
        ]
        assert output.interview_readiness_score < 50

    def test_minimal_input_works(self):
        data = _load_sample("edge_empty.json")
        engine = InterviewEngine(verbose=False)
        output = engine.run(data)

        assert output.status == TerminationReason.COMPLETED_ALL.value
        assert output.questions_attempted == 1
        assert output.interview_readiness_score > 0


class TestValidationFailure:
    """Test engine behavior with invalid inputs."""

    def test_empty_dict_fails(self):
        engine = InterviewEngine(verbose=False)
        output = engine.run({})
        assert output.status == TerminationReason.VALIDATION_FAILED.value
        assert output.interview_readiness_score == 0.0

    def test_missing_candidate_fails(self):
        engine = InterviewEngine(verbose=False)
        output = engine.run({
            "job_description": {"role": "Test", "required_skills": []},
            "interaction_events": [],
        })
        assert output.status == TerminationReason.VALIDATION_FAILED.value

    def test_invalid_json_string(self):
        engine = InterviewEngine(verbose=False)
        with pytest.raises(ValueError, match="Invalid JSON"):
            engine.run_from_json("not valid json {")

    def test_non_dict_input(self):
        engine = InterviewEngine(verbose=False)
        output = engine.run("a string, not a dict")
        assert output.status == TerminationReason.VALIDATION_FAILED.value


class TestOutputSerialization:
    """Test that output can be serialized to JSON."""

    def test_output_serializes_to_json(self):
        data = _load_sample("sample_input.json")
        engine = InterviewEngine(verbose=False)
        output = engine.run(data)

        json_str = json.dumps(output.to_dict(), indent=2)
        assert len(json_str) > 0

        # Parse it back
        parsed = json.loads(json_str)
        assert parsed["interview_readiness_score"] == output.interview_readiness_score

    def test_all_samples_produce_valid_json(self):
        for sample_file in SAMPLES_DIR.glob("*.json"):
            data = _load_sample(sample_file.name)
            engine = InterviewEngine(verbose=False)
            output = engine.run(data)
            json_str = json.dumps(output.to_dict(), indent=2)
            parsed = json.loads(json_str)
            assert "interview_readiness_score" in parsed
