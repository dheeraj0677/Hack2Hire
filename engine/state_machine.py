"""
Interview Engine — Finite State Machine orchestrator for interactive sessions.

This is the main entry point for processing an interactive interview.
It coordinates the LLM, scoring engine, adaptive logic,
and termination checker to produce the final output.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Dict, List, Optional, Tuple

from models.schema import (
    AdaptiveTrace,
    CategoryBreakdown,
    DifficultyLevel,
    InteractionEvent,
    InterviewInput,
    InterviewOutput,
    InterviewState,
    QuestionResult,
    TerminationReason,
    CandidateProfile,
    JobDescription,
    ScoringConfig,
    TerminationConfig,
    QuestionCategory
)
from engine.adaptive import AdaptiveEngine
from engine.scoring import ScoringEngine
from engine.termination import TerminationChecker
from engine.validator import InputValidator, ValidationError
from engine.llm_service import LLMService

logger = logging.getLogger(__name__)

class InterviewSession:
    """Holds state for an interactive interview session."""
    def __init__(self, session_id: str, candidate: CandidateProfile, jd: JobDescription):
        self.session_id = session_id
        self.candidate = candidate
        self.job_description = jd
        
        self.scoring_config = ScoringConfig()
        self.termination_config = TerminationConfig()
        
        self.state: InterviewState = InterviewState.INITIALIZED
        self.current_difficulty: DifficultyLevel = DifficultyLevel.from_str(jd.difficulty_preference)
        
        self.events: List[InteractionEvent] = []
        self.results: List[QuestionResult] = []
        self.adjustments: List[AdaptiveTrace] = []
        
        self.termination_reason: Optional[TerminationReason] = None
        self.current_question: Optional[InteractionEvent] = None


class InterviewEngine:
    """
    Finite State Machine that orchestrates the interactive interview simulation.
    """
    VERSION = "2.0.0"

    def __init__(self, llm_service: LLMService, verbose: bool = False):
        self.verbose = verbose
        self.llm = llm_service
        # In-memory session store for MVP
        self.sessions: Dict[str, InterviewSession] = {}

    def start_session(self, resume_text: str, jd_text: str) -> Dict[str, Any]:
        """Start a new interview session by analyzing resume and JD."""
        analysis = self.llm.analyze_resume_and_jd(resume_text, jd_text)
        
        candidate = CandidateProfile(
            candidate_id=str(uuid.uuid4()),
            name=analysis.get("candidate_name", "Candidate"),
            experience_years=float(analysis.get("experience_years", 0.0)),
            skills=analysis.get("candidate_skills", []),
            target_role=analysis.get("job_role", "Unknown Role")
        )
        
        jd = JobDescription(
            role=analysis.get("job_role", "Unknown Role"),
            required_skills=analysis.get("required_skills", []),
            min_experience=float(analysis.get("min_experience_required", 0.0)),
            difficulty_preference="medium"
        )
        
        session_id = str(uuid.uuid4())
        session = InterviewSession(session_id, candidate, jd)
        session.state = InterviewState.IN_PROGRESS
        
        # Generate first question
        q_text = self.llm.generate_question(
            jd=jd_text,
            resume=resume_text,
            difficulty=session.current_difficulty.value,
            category="technical",
            previous_questions=[]
        )
        
        event = InteractionEvent(
            question_id=f"Q1",
            question_text=q_text,
            difficulty_level=session.current_difficulty,
            category=QuestionCategory.TECHNICAL,
            candidate_response=None,
            time_taken_seconds=0
        )
        session.current_question = event
        self.sessions[session_id] = session
        
        return {
            "session_id": session_id,
            "analysis": analysis,
            "question": {
                "question_id": event.question_id,
                "text": event.question_text,
                "difficulty": event.difficulty_level.value,
                "category": event.category.value
            }
        }

    def submit_answer(self, session_id: str, answer_text: str, time_taken_seconds: float) -> Dict[str, Any]:
        """Process an answer, score it, check termination, adjust difficulty, generate next question."""
        if session_id not in self.sessions:
            raise ValueError(f"Session {session_id} not found.")
            
        session = self.sessions[session_id]
        if session.state in [InterviewState.TERMINATED, InterviewState.COMPLETED]:
            return {"status": session.state.value, "message": "Interview already ended."}
            
        event = session.current_question
        event.candidate_response = answer_text
        event.time_taken_seconds = time_taken_seconds
        
        session.state = InterviewState.EVALUATING
        
        # Evaluate using LLM
        eval_result = self.llm.evaluate_response(
            question=event.question_text,
            response=answer_text,
            jd=session.job_description.role
        )
        
        event.relevance_score = eval_result.get("relevance_score")
        event.depth_score = eval_result.get("depth_score")
        event.accuracy_score = eval_result.get("accuracy_score")
        event.clarity_score = eval_result.get("clarity_score")
        
        session.events.append(event)
        
        # Score the question locally
        scoring = ScoringEngine(session.scoring_config)
        result = scoring.score_question(event)
        session.results.append(result)
        
        # Check termination
        termination = TerminationChecker(session.termination_config)
        term_reason = termination.check(event, result, session.results)
        
        if term_reason:
            session.state = InterviewState.TERMINATED
            session.termination_reason = term_reason
            return {
                "status": "terminated",
                "reason": term_reason.value,
                "feedback": eval_result.get("feedback")
            }
            
        # Adaptive difficulty
        adaptive = AdaptiveEngine(session.current_difficulty)
        adaptive.adjustments = session.adjustments # Restore state
        new_diff = adaptive.evaluate(session.results)
        session.current_difficulty = new_diff
        session.adjustments = adaptive.adjustments
        
        # Generate next question
        session.state = InterviewState.IN_PROGRESS
        next_q_num = len(session.events) + 1
        
        # Simple category rotation
        cats = [QuestionCategory.TECHNICAL, QuestionCategory.BEHAVIORAL, QuestionCategory.SITUATIONAL]
        next_cat = cats[next_q_num % len(cats)]
        
        q_text = self.llm.generate_question(
            jd=session.job_description.role, # simplified for prompt length
            resume=session.candidate.skills,
            difficulty=session.current_difficulty.value,
            category=next_cat.value,
            previous_questions=[e.question_text for e in session.events]
        )
        
        next_event = InteractionEvent(
            question_id=f"Q{next_q_num}",
            question_text=q_text,
            difficulty_level=session.current_difficulty,
            category=next_cat,
            candidate_response=None,
            time_taken_seconds=0
        )
        session.current_question = next_event
        
        return {
            "status": "in_progress",
            "evaluation": eval_result,
            "next_question": {
                "question_id": next_event.question_id,
                "text": next_event.question_text,
                "difficulty": next_event.difficulty_level.value,
                "category": next_event.category.value
            }
        }

    def generate_report(self, session_id: str) -> Dict[str, Any]:
        """Generate the final report using the LLM and scoring engine."""
        if session_id not in self.sessions:
            raise ValueError(f"Session {session_id} not found.")
            
        session = self.sessions[session_id]
        scoring = ScoringEngine(session.scoring_config)
        
        skill_ratio, matched = scoring.compute_skill_match(session.candidate.skills, session.job_description.required_skills)
        irs = scoring.compute_interview_readiness_score(session.results, skill_ratio)
        breakdowns = scoring.compute_category_breakdown(session.results)
        
        # Generate final qualitative feedback via LLM
        report_data = {
            "readiness_score": irs,
            "questions_answered": len(session.results),
            "categories": [c.to_dict() for c in breakdowns]
        }
        
        qualitative_feedback = self.llm.generate_final_report(report_data)
        
        return {
            "session_id": session_id,
            "candidate_name": session.candidate.name,
            "readiness_score": irs,
            "skill_match": matched,
            "breakdowns": [c.to_dict() for c in breakdowns],
            "qualitative": qualitative_feedback
        }
