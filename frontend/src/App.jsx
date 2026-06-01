import React, { useState, useEffect } from 'react';
import { Play, Send, CheckCircle, AlertTriangle, FileText, Briefcase, Key, RefreshCcw } from 'lucide-react';

const API_URL = 'http://localhost:8000/api/interview';

function App() {
  const [appState, setAppState] = useState('setup'); // setup, interview, report
  const [apiKey, setApiKey] = useState('');
  const [resume, setResume] = useState('');
  const [jd, setJd] = useState('');
  const [sessionId, setSessionId] = useState(null);
  
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  
  // Interview State
  const [currentQuestion, setCurrentQuestion] = useState(null);
  const [answerText, setAnswerText] = useState('');
  const [timeLeft, setTimeLeft] = useState(120);
  const [evaluation, setEvaluation] = useState(null);
  const [analysis, setAnalysis] = useState(null);

  // Report State
  const [reportData, setReportData] = useState(null);

  useEffect(() => {
    let timer;
    if (appState === 'interview' && timeLeft > 0 && !loading && !evaluation) {
      timer = setInterval(() => setTimeLeft(t => t - 1), 1000);
    }
    return () => clearInterval(timer);
  }, [appState, timeLeft, loading, evaluation]);

  const startInterview = async () => {
    if (!resume || !jd) {
      setError("Please provide both Resume and Job Description.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_URL}/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ api_key: apiKey, resume_text: resume, job_description: jd })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Failed to start");
      
      setSessionId(data.session_id);
      setAnalysis(data.analysis);
      setCurrentQuestion(data.question);
      setAppState('interview');
      setTimeLeft(120);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const submitAnswer = async () => {
    if (!answerText.trim()) {
      setError("Please provide an answer.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const timeTaken = 120 - timeLeft;
      const res = await fetch(`${API_URL}/answer`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, answer_text: answerText, time_taken_seconds: timeTaken })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Failed to submit");
      
      setEvaluation(data.evaluation || { feedback: data.feedback });
      
      if (data.status === 'terminated') {
        setTimeout(() => fetchReport(), 3000);
      } else {
        setTimeout(() => {
          setCurrentQuestion(data.next_question);
          setAnswerText('');
          setEvaluation(null);
          setTimeLeft(120);
        }, 3000);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const fetchReport = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/report/${sessionId}`);
      const data = await res.json();
      setReportData(data);
      setAppState('report');
    } catch (err) {
      setError("Failed to fetch report.");
    } finally {
      setLoading(false);
    }
  };

  if (appState === 'setup') {
    return (
      <div className="min-h-screen bg-gradient-to-br from-indigo-50 via-white to-purple-50 flex items-center justify-center p-6">
        <div className="w-full max-w-4xl bg-white/70 backdrop-blur-xl rounded-2xl shadow-xl border border-white/50 overflow-hidden flex flex-col md:flex-row">
          
          <div className="md:w-2/5 bg-indigo-600 p-8 text-white flex flex-col justify-between">
            <div>
              <h1 className="text-3xl font-bold mb-4 tracking-tight">AI Interviewer</h1>
              <p className="text-indigo-100 mb-8 leading-relaxed">
                Experience a dynamic, adaptive technical interview powered by Gemini. 
                Our AI analyzes your resume, asks tailored questions, and evaluates your responses in real-time.
              </p>
              
              <div className="space-y-4">
                <div className="flex items-center gap-3 bg-indigo-700/50 p-3 rounded-lg">
                  <Briefcase size={20} className="text-indigo-200" />
                  <span className="text-sm">Job Description Analysis</span>
                </div>
                <div className="flex items-center gap-3 bg-indigo-700/50 p-3 rounded-lg">
                  <FileText size={20} className="text-indigo-200" />
                  <span className="text-sm">Resume Alignment</span>
                </div>
                <div className="flex items-center gap-3 bg-indigo-700/50 p-3 rounded-lg">
                  <RefreshCcw size={20} className="text-indigo-200" />
                  <span className="text-sm">Adaptive Difficulty</span>
                </div>
              </div>
            </div>
          </div>

          <div className="md:w-3/5 p-8">
            <h2 className="text-2xl font-semibold text-slate-800 mb-6">Setup Session</h2>
            
            {error && (
              <div className="mb-6 p-4 bg-red-50 text-red-700 rounded-lg flex items-start gap-3 border border-red-100">
                <AlertTriangle size={20} className="mt-0.5" />
                <span className="text-sm">{error}</span>
              </div>
            )}

            <div className="space-y-5">
              <div>
                <label className="flex items-center gap-2 text-sm font-medium text-slate-700 mb-1">
                  <Key size={16} /> Gemini API Key (Optional if set in backend)
                </label>
                <input 
                  type="password"
                  className="w-full p-3 rounded-lg border border-slate-200 bg-slate-50 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none transition-all"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder="AIzaSy..."
                />
              </div>

              <div>
                <label className="flex items-center gap-2 text-sm font-medium text-slate-700 mb-1">
                  <Briefcase size={16} /> Job Description
                </label>
                <textarea 
                  className="w-full p-3 rounded-lg border border-slate-200 bg-slate-50 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none transition-all h-32 resize-none"
                  value={jd}
                  onChange={(e) => setJd(e.target.value)}
                  placeholder="Paste the target job description here..."
                ></textarea>
              </div>

              <div>
                <label className="flex items-center gap-2 text-sm font-medium text-slate-700 mb-1">
                  <FileText size={16} /> Candidate Resume (Text)
                </label>
                <textarea 
                  className="w-full p-3 rounded-lg border border-slate-200 bg-slate-50 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none transition-all h-32 resize-none"
                  value={resume}
                  onChange={(e) => setResume(e.target.value)}
                  placeholder="Paste the candidate's resume text here..."
                ></textarea>
              </div>

              <button 
                onClick={startInterview}
                disabled={loading}
                className="w-full flex items-center justify-center gap-2 py-3 px-4 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg font-medium transition-all disabled:opacity-70 disabled:cursor-not-allowed shadow-lg shadow-indigo-200 mt-2"
              >
                {loading ? (
                  <RefreshCcw className="animate-spin" size={20} />
                ) : (
                  <>
                    <Play size={20} />
                    Start Interview
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (appState === 'interview' && currentQuestion) {
    const isOvertime = timeLeft === 0;
    
    return (
      <div className="min-h-screen bg-slate-50 flex flex-col">
        {/* Header */}
        <header className="bg-white border-b border-slate-200 px-6 py-4 flex justify-between items-center sticky top-0 z-10 shadow-sm">
          <div className="flex items-center gap-4">
            <div className="w-10 h-10 bg-indigo-100 text-indigo-600 rounded-full flex items-center justify-center font-bold text-xl">
              AI
            </div>
            <div>
              <h2 className="font-semibold text-slate-800">Mock Interview</h2>
              <p className="text-xs text-slate-500 capitalize">
                {currentQuestion.category} • {currentQuestion.difficulty}
              </p>
            </div>
          </div>
          
          <div className="flex items-center gap-6">
            <div className="text-right hidden md:block">
              <p className="text-xs font-medium text-slate-500">Candidate</p>
              <p className="font-semibold text-slate-800">{analysis?.candidate_name}</p>
            </div>
            
            <div className={`px-4 py-2 rounded-lg font-mono font-bold flex items-center gap-2 ${
              isOvertime ? 'bg-red-100 text-red-700' : timeLeft < 30 ? 'bg-amber-100 text-amber-700' : 'bg-slate-100 text-slate-700'
            }`}>
              {Math.floor(timeLeft / 60)}:{(timeLeft % 60).toString().padStart(2, '0')}
            </div>
            
            <button 
              onClick={fetchReport}
              className="text-sm font-medium text-slate-500 hover:text-slate-800 transition-colors"
            >
              End Early
            </button>
          </div>
        </header>

        {/* Main Content */}
        <main className="flex-1 max-w-4xl w-full mx-auto p-6 flex flex-col gap-6">
          
          {/* Question Card */}
          <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6">
            <div className="flex gap-4">
              <div className="mt-1">
                <div className="w-8 h-8 bg-indigo-600 text-white rounded-full flex items-center justify-center">
                  <Play size={14} fill="currentColor" />
                </div>
              </div>
              <div className="flex-1">
                <h3 className="text-lg font-medium text-slate-900 leading-relaxed">
                  {currentQuestion.text}
                </h3>
              </div>
            </div>
          </div>

          {/* Evaluation Banner (shows between questions) */}
          {evaluation && (
            <div className="bg-green-50 border border-green-200 rounded-2xl p-6 shadow-sm flex items-start gap-4 animate-in fade-in slide-in-from-bottom-4">
              <CheckCircle className="text-green-600 shrink-0" size={24} />
              <div>
                <h4 className="font-semibold text-green-800 mb-1">Response Evaluated</h4>
                <p className="text-green-700 text-sm mb-3">{evaluation.feedback}</p>
                {evaluation.relevance_score && (
                  <div className="flex flex-wrap gap-4 text-sm font-medium text-green-800">
                    <span>Relevance: {evaluation.relevance_score}/10</span>
                    <span>Depth: {evaluation.depth_score}/10</span>
                    <span>Accuracy: {evaluation.accuracy_score}/10</span>
                    <span>Clarity: {evaluation.clarity_score}/10</span>
                  </div>
                )}
                <p className="text-xs text-green-600 mt-3 font-medium animate-pulse">
                  Preparing next question...
                </p>
              </div>
            </div>
          )}

          {/* Answer Area */}
          <div className="flex-1 flex flex-col">
            <div className="relative flex-1 bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden focus-within:ring-2 focus-within:ring-indigo-500 focus-within:border-indigo-500 transition-all">
              <textarea
                className="w-full h-full min-h-[200px] p-6 resize-none outline-none text-slate-700 leading-relaxed bg-transparent"
                placeholder="Type your answer here... Take a deep breath."
                value={answerText}
                onChange={(e) => setAnswerText(e.target.value)}
                disabled={loading || !!evaluation}
              />
              
              <div className="absolute bottom-4 right-4">
                <button
                  onClick={submitAnswer}
                  disabled={loading || !!evaluation || !answerText.trim()}
                  className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white px-6 py-2.5 rounded-full font-medium transition-all disabled:opacity-50 shadow-md"
                >
                  {loading ? (
                    <RefreshCcw className="animate-spin" size={18} />
                  ) : (
                    <>
                      Submit <Send size={16} />
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
          
          {error && (
            <div className="p-4 bg-red-50 text-red-700 rounded-lg text-sm border border-red-100 flex items-center gap-2">
              <AlertTriangle size={16} /> {error}
            </div>
          )}
          
        </main>
      </div>
    );
  }

  if (appState === 'report' && reportData) {
    const qual = reportData.qualitative || {};
    return (
      <div className="min-h-screen bg-slate-50 py-12 px-6">
        <div className="max-w-5xl mx-auto space-y-8">
          
          <header className="text-center space-y-4">
            <h1 className="text-3xl font-bold text-slate-900">Interview Readiness Report</h1>
            <p className="text-slate-500">Prepared for {reportData.candidate_name}</p>
          </header>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            
            {/* Score Card */}
            <div className="md:col-span-1 bg-white rounded-2xl shadow-sm border border-slate-200 p-8 flex flex-col items-center justify-center text-center">
              <h3 className="text-lg font-medium text-slate-500 mb-4">Final Readiness Score</h3>
              <div className="relative w-40 h-40 flex items-center justify-center rounded-full border-8 border-indigo-100 mb-4">
                <span className="text-5xl font-bold text-indigo-600">{reportData.readiness_score}</span>
              </div>
              <div className={`mt-2 px-4 py-1.5 rounded-full text-sm font-semibold ${
                qual.hiring_readiness_indicator?.includes('Strong') ? 'bg-green-100 text-green-700' :
                qual.hiring_readiness_indicator?.includes('Hire') ? 'bg-blue-100 text-blue-700' :
                qual.hiring_readiness_indicator?.includes('Improve') ? 'bg-amber-100 text-amber-700' :
                'bg-red-100 text-red-700'
              }`}>
                {qual.hiring_readiness_indicator || "Evaluation Complete"}
              </div>
            </div>

            {/* Qualitative Feedback */}
            <div className="md:col-span-2 bg-white rounded-2xl shadow-sm border border-slate-200 p-8">
              <h3 className="text-xl font-semibold text-slate-800 mb-4">Actionable Feedback</h3>
              <p className="text-slate-600 leading-relaxed mb-8">
                {qual.actionable_feedback || "No feedback generated."}
              </p>
              
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                <div>
                  <h4 className="flex items-center gap-2 font-medium text-green-700 mb-3">
                    <CheckCircle size={18} /> Key Strengths
                  </h4>
                  <ul className="space-y-2">
                    {(qual.strengths || []).map((s, i) => (
                      <li key={i} className="text-sm text-slate-600 flex items-start gap-2">
                        <span className="text-green-500 mt-1">•</span> {s}
                      </li>
                    ))}
                  </ul>
                </div>
                <div>
                  <h4 className="flex items-center gap-2 font-medium text-amber-700 mb-3">
                    <AlertTriangle size={18} /> Areas to Improve
                  </h4>
                  <ul className="space-y-2">
                    {(qual.weaknesses || []).map((w, i) => (
                      <li key={i} className="text-sm text-slate-600 flex items-start gap-2">
                        <span className="text-amber-500 mt-1">•</span> {w}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>
          </div>

          {/* Breakdown List */}
          <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-8">
            <h3 className="text-xl font-semibold text-slate-800 mb-6">Category Breakdown</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
              {reportData.breakdowns?.map((cat, i) => (
                <div key={i} className="p-4 rounded-xl border border-slate-100 bg-slate-50">
                  <h4 className="font-medium text-slate-700 capitalize mb-2">{cat.category}</h4>
                  <div className="flex justify-between items-end mb-2">
                    <span className="text-2xl font-bold text-slate-900">{cat.percentage.toFixed(0)}%</span>
                    <span className="text-xs text-slate-500">{cat.questions_count} questions</span>
                  </div>
                  <div className="w-full bg-slate-200 rounded-full h-1.5">
                    <div className="bg-indigo-500 h-1.5 rounded-full" style={{ width: `${cat.percentage}%` }}></div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="text-center">
            <button 
              onClick={() => window.location.reload()}
              className="text-indigo-600 font-medium hover:text-indigo-800 transition-colors"
            >
              Start New Interview
            </button>
          </div>

        </div>
      </div>
    );
  }

  return null;
}

export default App;
