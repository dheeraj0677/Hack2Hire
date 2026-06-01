import os
import json
import google.generativeai as genai
from typing import Dict, Any, List

class LLMService:
    def __init__(self, api_key: str = None):
        """Initialize the Gemini LLM service."""
        key = api_key or os.environ.get("GEMINI_API_KEY")
        if not key:
            raise ValueError("GEMINI_API_KEY is missing.")
        genai.configure(api_key=key)
        # Use gemini-1.5-flash as it is fast and suitable for this task
        self.model = genai.GenerativeModel("gemini-1.5-flash")

    def _extract_json(self, response_text: str) -> dict:
        """Helper to extract JSON from markdown code blocks if present."""
        text = response_text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError as e:
            print(f"Failed to parse JSON: {e}")
            print(f"Raw response: {response_text}")
            return {}

    def analyze_resume_and_jd(self, resume: str, jd: str) -> Dict[str, Any]:
        """Analyze Resume and JD to extract skills, experience and role alignment."""
        prompt = f"""
        You are an expert technical recruiter. Analyze the following Resume and Job Description (JD).
        
        Job Description:
        {jd}
        
        Resume:
        {resume}
        
        Provide your analysis in the exact following JSON format, and nothing else:
        {{
            "candidate_name": "extracted name or Unknown",
            "experience_years": 4.5,
            "candidate_skills": ["Python", "React", "AWS"],
            "job_role": "extracted role from JD",
            "required_skills": ["Python", "Docker", "AWS"],
            "min_experience_required": 3.0,
            "skill_match_ratio": 0.8,
            "analysis_summary": "Brief summary of how well they fit the role."
        }}
        """
        response = self.model.generate_content(prompt)
        return self._extract_json(response.text)

    def generate_question(
        self, 
        jd: str, 
        resume: str, 
        difficulty: str, 
        category: str, 
        previous_questions: List[str]
    ) -> str:
        """Generate a tailored interview question."""
        prompt = f"""
        You are an AI Technical Interviewer. Generate ONE highly relevant interview question for a candidate.
        
        Job Description:
        {jd}
        
        Candidate Resume:
        {resume}
        
        Category: {category} (e.g., technical, behavioral, situational)
        Difficulty Level: {difficulty} (e.g., easy, medium, hard)
        
        Previous Questions Asked (do not repeat these or ask very similar questions):
        {json.dumps(previous_questions)}
        
        Requirements for the question:
        - Must be directly related to the candidate's skills and the JD.
        - Must be exactly ONE clear question.
        - Do not include greetings, introductions, or any other text. Just the question.
        """
        response = self.model.generate_content(prompt)
        return response.text.strip()

    def evaluate_response(
        self, 
        question: str, 
        response: str, 
        jd: str
    ) -> Dict[str, float]:
        """Evaluate the candidate's response to a question."""
        prompt = f"""
        You are an expert technical interviewer evaluating a candidate's response.
        
        Job Description Context:
        {jd}
        
        Question:
        {question}
        
        Candidate's Response:
        {response}
        
        Evaluate the response on the following criteria on a scale of 0.0 to 10.0:
        1. Relevance: How well did the response address the specific question?
        2. Depth: How deep and comprehensive was the answer?
        3. Accuracy: How technically or factually correct was the answer?
        4. Clarity: How clearly and structured was the communication?
        
        Provide the result in the exact following JSON format, and nothing else:
        {{
            "relevance_score": 8.5,
            "depth_score": 7.0,
            "accuracy_score": 9.0,
            "clarity_score": 8.0,
            "feedback": "Brief 1-2 sentence feedback for the candidate."
        }}
        """
        resp = self.model.generate_content(prompt)
        result = self._extract_json(resp.text)
        
        # Ensure fallback defaults if extraction fails
        return {
            "relevance_score": float(result.get("relevance_score", 5.0)),
            "depth_score": float(result.get("depth_score", 5.0)),
            "accuracy_score": float(result.get("accuracy_score", 5.0)),
            "clarity_score": float(result.get("clarity_score", 5.0)),
            "feedback": str(result.get("feedback", "Thank you for your response."))
        }

    def generate_final_report(self, interview_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate final qualitative report based on interview results."""
        prompt = f"""
        You are a Senior Hiring Manager. Based on the following interview performance data, generate a final feedback report.
        
        Data:
        {json.dumps(interview_data, indent=2)}
        
        Provide the result in the exact following JSON format, and nothing else:
        {{
            "strengths": ["Strength 1", "Strength 2"],
            "weaknesses": ["Area to improve 1", "Area to improve 2"],
            "actionable_feedback": "Detailed paragraph of feedback for the candidate to improve.",
            "hiring_readiness_indicator": "Strong Hire / Hire / Average / Needs Improvement / Do Not Hire"
        }}
        """
        response = self.model.generate_content(prompt)
        return self._extract_json(response.text)
