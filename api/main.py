from fastapi import FastAPI, HTTPException, Body, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, Optional
import os

from engine.llm_service import LLMService
from engine.state_machine import InterviewEngine

app = FastAPI(title="AI Mock Interview Platform API")

# Setup CORS for the React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global engine instance (for MVP state management in-memory)
# In production, state would be saved to a database (Redis/Postgres).
llm_service = LLMService(api_key=os.environ.get("GEMINI_API_KEY", "placeholder"))
engine = InterviewEngine(llm_service=llm_service, verbose=True)

class StartRequest(BaseModel):
    api_key: str
    resume_text: str
    job_description: str

class AnswerRequest(BaseModel):
    session_id: str
    answer_text: str
    time_taken_seconds: float

@app.post("/api/interview/start")
def start_interview(request: StartRequest):
    try:
        # Re-initialize LLM if API key is provided
        if request.api_key and request.api_key != "placeholder":
            engine.llm = LLMService(api_key=request.api_key)
            
        result = engine.start_session(request.resume_text, request.job_description)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/interview/answer")
def submit_answer(request: AnswerRequest):
    try:
        result = engine.submit_answer(
            request.session_id, 
            request.answer_text, 
            request.time_taken_seconds
        )
        return result
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/interview/report/{session_id}")
def get_report(session_id: str):
    try:
        report = engine.generate_report(session_id)
        return report
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
