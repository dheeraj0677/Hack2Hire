# AI-Powered Mock Interview Platform

An **Interactive, AI-driven Mock Interview Platform** built to satisfy the Unstop Hack2Hire problem statement. It uses the Gemini API (LLM) to dynamically analyze a candidate's resume, generate contextual interview questions, evaluate answers, adapt difficulty, enforce time constraints, and produce a comprehensive Interview Readiness Score.

## Tech Stack
- **Backend:** Python + FastAPI (Stateful FSM Engine)
- **AI Integration:** Google Gemini API (`gemini-1.5-flash`)
- **Frontend:** React + Vite + TailwindCSS

---

## Capabilities Implemented
1. **Resume & JD Analysis:** Extracts skills and computes a skill match ratio.
2. **Dynamic Question Generation:** Questions are generated on the fly by Gemini based on the JD, candidate skills, category, and difficulty.
3. **Real-time Evaluation:** The LLM evaluates responses across 4 strict criteria: **Accuracy, Clarity, Depth, and Relevance** (0–10 scale).
4. **Time Constraints:** The frontend runs a strict 120-second timer. The backend penalizes responses that are too fast (<30%) or slow/overtime.
5. **Adaptive Difficulty:** A sliding-window system (last 3 questions) increases difficulty for strong responses and reduces it for weak ones.
6. **Early Termination:** Terminates early if the candidate provides no response, goes significantly over time, or performs poorly consecutively.

## How to Run Locally

### Prerequisites
- Python 3.10+
- Node.js 18+
- A Google Gemini API Key (or input it via the UI)

### 1. Start the Backend (FastAPI)

```bash
cd Hack2Hire
python -m venv .venv
# Activate venv: .venv\Scripts\activate (Windows) or source .venv/bin/activate (Mac/Linux)
pip install fastapi uvicorn google-generativeai pydantic
python -m uvicorn api.main:app --reload --port 8000
```
*The backend API will run on `http://localhost:8000`.*

### 2. Start the Frontend (React/Vite)

```bash
cd Hack2Hire/frontend
npm install
npm run dev

*The frontend UI will run on `http://localhost:5173`.*



## Application Flow

1. **Setup Screen:** Input your Gemini API Key, target Job Description, and candidate Resume (text).
2. **The Interview:** The AI will introduce the first question. You have 120 seconds to type your response. When you submit, the AI evaluates your answer, shows the feedback/scores momentarily, adjusts the difficulty, and asks the next question.
3. **Final Report:** The interview ends when you complete the max questions or trigger an early termination rule. You are presented with a final dashboard showing your Interview Readiness Score, Hiring Readiness Indicator, and detailed feedback.
