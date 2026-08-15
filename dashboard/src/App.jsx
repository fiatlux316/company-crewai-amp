import React, { useState, useEffect, useRef } from 'react';
import { 
  Play, 
  History, 
  Settings, 
  Key, 
  Cpu, 
  CheckCircle2, 
  XCircle, 
  Loader2, 
  Terminal, 
  ArrowRight, 
  ChevronRight,
  Database,
  ExternalLink,
  Code
} from 'lucide-react';

export default function App() {
  // 1. 상태 정의 (State Definitions)
  const [apiKey, setApiKey] = useState(
    () => localStorage.getItem('CREWAI_API_KEY') || 'super-secret-company-key'
  );
  const [apiEndpoint, setApiEndpoint] = useState(
    () => localStorage.getItem('CREWAI_API_ENDPOINT') || window.location.origin
  );
  const [crews, setCrews] = useState([]);
  const [tasks, setTasks] = useState([]);
  
  const [activeTab, setActiveTab] = useState('crews'); // 'crews' | 'history'
  const [selectedCrew, setSelectedCrew] = useState(null);
  const [inputsJson, setInputsJson] = useState('{\n  "topic": "SaaS Marketing"\n}');
  
  const [selectedTask, setSelectedTask] = useState(null);
  const [isExecuting, setIsExecuting] = useState(false);
  const [pollingTaskId, setPollingTaskId] = useState(null);
  const [errorMsg, setErrorMsg] = useState('');

  // 2. 환경 설정 자동 저장 (Auto-save configuration)
  useEffect(() => {
    localStorage.setItem('CREWAI_API_KEY', apiKey);
  }, [apiKey]);

  useEffect(() => {
    localStorage.setItem('CREWAI_API_ENDPOINT', apiEndpoint);
  }, [apiEndpoint]);

  // 3. API 공통 요청 유틸리티
  const fetchWithAuth = async (path, options = {}) => {
    const url = `${apiEndpoint.replace(/\/$/, '')}${path}`;
    const headers = {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${apiKey}`,
      ...options.headers,
    };
    
    const response = await fetch(url, { ...options, headers });
    if (!response.ok) {
      const errorText = await response.text();
      let parsedError;
      try {
        parsedError = JSON.parse(errorText);
      } catch (e) {
        parsedError = { detail: errorText };
      }
      throw new Error(parsedError.detail || `HTTP Error ${response.status}`);
    }
    return response.json();
  };

  // 4. 데이터 로드 (Load Crews & Task History)
  const loadCrews = async () => {
    try {
      setErrorMsg('');
      const data = await fetchWithAuth('/api/v1/crews');
      setCrews(data);
      if (data.length > 0 && !selectedCrew) {
        setSelectedCrew(data[0]);
      }
    } catch (e) {
      console.error(e);
      setErrorMsg(`Failed to load crews: ${e.message}. Please check API Key & URL.`);
    }
  };

  const loadTasks = async () => {
    try {
      const data = await fetchWithAuth('/api/v1/tasks');
      setTasks(data);
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    loadCrews();
    loadTasks();
  }, [apiEndpoint, apiKey]);

  // 5. 비동기 작업 폴링 루프 (Polling Mechanism)
  useEffect(() => {
    let intervalId = null;

    if (pollingTaskId) {
      intervalId = setInterval(async () => {
        try {
          const task = await fetchWithAuth(`/api/v1/tasks/${pollingTaskId}`);
          
          // 태스크 상세 정보 업데이트
          setSelectedTask(task);
          
          // 상태가 SUCCESS 또는 FAILED 이면 폴링 정지
          if (task.status === 'SUCCESS' || task.status === 'FAILED') {
            setPollingTaskId(null);
            setIsExecuting(false);
            loadTasks(); // 히스토리 갱신
          }
        } catch (e) {
          console.error('Polling error:', e);
          setPollingTaskId(null);
          setIsExecuting(false);
        }
      }, 2000);
    }

    return () => {
      if (intervalId) clearInterval(intervalId);
    };
  }, [pollingTaskId]);

  // 6. Crew 실행 요청 (Trigger execution)
  const handleKickoff = async () => {
    if (!selectedCrew) return;
    setErrorMsg('');
    setIsExecuting(true);

    let parsedInputs;
    try {
      parsedInputs = JSON.parse(inputsJson);
    } catch (e) {
      setErrorMsg('Inputs must be a valid JSON format.');
      setIsExecuting(false);
      return;
    }

    try {
      const result = await fetchWithAuth(`/api/v1/crews/${selectedCrew.crew_id}/kickoff`, {
        method: 'POST',
        body: JSON.stringify({ inputs: parsedInputs }),
      });

      // 폴링 시작 설정
      setPollingTaskId(result.task_id);
      
      // 바로 작업 상세화면 및 모니터링 탭으로 상태 전환
      setSelectedTask({
        id: result.task_id,
        crew_id: selectedCrew.crew_id,
        status: 'PENDING',
        inputs: parsedInputs,
        created_at: new Date().toISOString()
      });
      setActiveTab('history');
    } catch (e) {
      setErrorMsg(`Failed to kickoff crew: ${e.message}`);
      setIsExecuting(false);
    }
  };

  const getStatusBadgeClass = (status) => {
    switch (status) {
      case 'PENDING': return 'badge-pending';
      case 'RUNNING': return 'badge-running';
      case 'SUCCESS': return 'badge-success';
      case 'FAILED': return 'badge-failed';
      default: return 'badge-pending';
    }
  };

  const formatDate = (isoString) => {
    if (!isoString) return '-';
    const date = new Date(isoString);
    return date.toLocaleString();
  };

  return (
    <div className="app-container">
      {/* SIDEBAR NAVIGATION */}
      <aside className="sidebar">
        <div className="logo-section">
          <span className="logo-icon">🚀</span>
          <div>
            <h1 className="logo-title">CrewAI AMP</h1>
            <p className="logo-subtitle">Company Private Platform</p>
          </div>
        </div>

        <ul className="nav-menu">
          <li 
            className={`nav-item ${activeTab === 'crews' ? 'active' : ''}`}
            onClick={() => setActiveTab('crews')}
          >
            <Play size={18} />
            <span>Crews Executer</span>
          </li>
          <li 
            className={`nav-item ${activeTab === 'history' ? 'active' : ''}`}
            onClick={() => {
              setActiveTab('history');
              loadTasks(); // 탭 이동 시 최신 내역 조회
            }}
          >
            <History size={18} />
            <span>Execution History</span>
          </li>
        </ul>

        {/* SETTINGS CARD IN SIDEBAR */}
        <div className="sidebar-footer">
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            <span style={{ fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
              <Settings size={12} /> Server Settings
            </span>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
              <label style={{ fontSize: '0.65rem' }}>ENDPOINT</label>
              <input 
                type="text" 
                className="input-field" 
                style={{ width: '100%', fontSize: '0.75rem', padding: '0.35rem' }}
                value={apiEndpoint} 
                onChange={(e) => setApiEndpoint(e.target.value)} 
              />
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
              <label style={{ fontSize: '0.65rem' }}>API BEARER KEY</label>
              <input 
                type="password" 
                className="input-field" 
                style={{ width: '100%', fontSize: '0.75rem', padding: '0.35rem' }}
                value={apiKey} 
                onChange={(e) => setApiKey(e.target.value)} 
              />
            </div>
          </div>
          <p style={{ marginTop: '1.5rem', fontSize: '0.65rem' }}>© 2026 MyCompany Inc.</p>
        </div>
      </aside>

      {/* MAIN CONTENT AREA */}
      <main className="main-content">
        
        {/* Error message banner */}
        {errorMsg && (
          <div className="auth-banner" style={{ borderColor: 'var(--accent-error)', backgroundColor: 'rgba(239,68,68,0.05)' }}>
            <span style={{ color: 'var(--accent-error)', display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.9rem' }}>
              <XCircle size={16} /> {errorMsg}
            </span>
            <button className="btn btn-secondary" style={{ padding: '0.25rem 0.5rem', fontSize: '0.75rem' }} onClick={() => setErrorMsg('')}>Dismiss</button>
          </div>
        )}

        {/* 1. CREWS EXECUTER TAB */}
        {activeTab === 'crews' && (
          <div>
            <div className="content-header">
              <div>
                <h2 className="header-title">Crews Executer</h2>
                <p className="header-subtitle">Scan & execute agent workflows in the crews/ directory dynamically.</p>
              </div>
            </div>

            <div className="execution-container">
              {/* Left Side: Dynamic Crew list */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
                <h3 style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--text-secondary)' }}>Available Crews ({crews.length})</h3>
                {crews.length === 0 ? (
                  <div className="card" style={{ cursor: 'default' }}>
                    <p style={{ color: 'var(--text-muted)', textAlign: 'center', padding: '2rem 0' }}>
                      No crews found. Add directories under crews/ folder.
                    </p>
                  </div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                    {crews.map((crew) => (
                      <div 
                        key={crew.crew_id} 
                        className={`card ${selectedCrew?.crew_id === crew.crew_id ? 'active' : ''}`}
                        style={{ 
                          borderColor: selectedCrew?.crew_id === crew.crew_id ? 'var(--accent-primary)' : 'var(--border-color)',
                          backgroundColor: selectedCrew?.crew_id === crew.crew_id ? 'var(--bg-tertiary)' : 'var(--bg-secondary)'
                        }}
                        onClick={() => setSelectedCrew(crew)}
                      >
                        <div className="card-header">
                          <div>
                            <span className="card-title" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                              <Cpu size={16} className="text-accent" style={{ color: 'var(--accent-primary)' }} />
                              {crew.display_name}
                            </span>
                            <span className="card-meta" style={{ display: 'block', marginTop: '0.25rem', fontFamily: 'var(--font-mono)' }}>
                              id: {crew.crew_id}
                            </span>
                          </div>
                          <ChevronRight size={18} style={{ color: 'var(--text-muted)' }} />
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Right Side: Inputs & Run Trigger Form */}
              {selectedCrew && (
                <div className="panel">
                  <h3 className="panel-title">
                    <Terminal size={18} style={{ color: 'var(--accent-primary)' }} />
                    Trigger: {selectedCrew.display_name}
                  </h3>

                  <div className="form-group">
                    <label className="form-label">INPUT VARIABLES (JSON)</label>
                    <textarea 
                      className="textarea-field"
                      value={inputsJson}
                      onChange={(e) => setInputsJson(e.target.value)}
                      placeholder='{ "topic": "SaaS Marketing" }'
                    />
                  </div>

                  <button 
                    className="btn btn-primary" 
                    onClick={handleKickoff}
                    disabled={isExecuting}
                    style={{ width: '100%', height: '46px' }}
                  >
                    {isExecuting ? (
                      <>
                        <Loader2 size={16} className="animate-spin" style={{ animation: 'spin 1.5s linear infinite' }} />
                        <span>Kicking off Agent Crew...</span>
                      </>
                    ) : (
                      <>
                        <Play size={16} />
                        <span>Kickoff Agent Crew</span>
                      </>
                    )}
                  </button>
                </div>
              )}
            </div>
          </div>
        )}

        {/* 2. HISTORY & DETAILED VIEW TAB */}
        {activeTab === 'history' && (
          <div>
            <div className="content-header">
              <div>
                <h2 className="header-title">Run History & Control</h2>
                <p className="header-subtitle">Monitor real-time task statuses and review historical LLM execution outputs.</p>
              </div>
            </div>

            <div className="execution-container" style={{ gridTemplateColumns: '380px 1fr' }}>
              {/* Left Column: Tasks history selection */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                <h3 style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--text-secondary)' }}>Execution Records</h3>
                
                {pollingTaskId && (
                  <div 
                    className="card monitoring-card running"
                    style={{ 
                      borderColor: 'var(--accent-primary)',
                      backgroundColor: 'rgba(59, 130, 246, 0.03)'
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontSize: '0.85rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        <Loader2 size={14} className="animate-spin" style={{ animation: 'spin 1.5s linear infinite', color: 'var(--accent-primary)' }} />
                        Active Polling...
                      </span>
                      <span className="card-badge badge-running">Running</span>
                    </div>
                    <span style={{ fontSize: '0.75rem', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                      id: {pollingTaskId.substring(0, 8)}...
                    </span>
                  </div>
                )}

                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', maxHeight: '60vh', overflowY: 'auto' }}>
                  {tasks.length === 0 ? (
                    <p style={{ color: 'var(--text-muted)', textAlign: 'center', padding: '1rem' }}>No task logs available.</p>
                  ) : (
                    tasks.map((task) => (
                      <div 
                        key={task.id} 
                        className={`card ${selectedTask?.id === task.id ? 'active' : ''}`}
                        style={{ 
                          padding: '1rem',
                          borderColor: selectedTask?.id === task.id ? 'var(--accent-primary)' : 'var(--border-color)',
                          backgroundColor: selectedTask?.id === task.id ? 'var(--bg-tertiary)' : 'var(--bg-secondary)'
                        }}
                        onClick={() => setSelectedTask(task)}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <span style={{ fontWeight: 600, fontSize: '0.9rem' }}>
                            {task.crew_id}
                          </span>
                          <span className={`card-badge ${getStatusBadgeClass(task.status)}`}>
                            {task.status}
                          </span>
                        </div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.5rem' }}>
                          <span style={{ fontFamily: 'var(--font-mono)' }}>{task.id.substring(0, 8)}...</span>
                          <span>{formatDate(task.created_at)}</span>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>

              {/* Right Column: Detailed View */}
              <div className="panel" style={{ minHeight: '500px' }}>
                {selectedTask ? (
                  <div className="result-viewer">
                    {/* Task Metadata Header */}
                    <div style={{ borderBottom: '1px solid var(--border-color)', paddingBottom: '1.25rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
                      <div>
                        <span style={{ display: 'block', color: 'var(--text-muted)', fontSize: '0.75rem', fontFamily: 'var(--font-mono)' }}>
                          TASK ID: {selectedTask.id}
                        </span>
                        <h3 style={{ fontSize: '1.35rem', fontWeight: 700, marginTop: '0.25rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                          {selectedTask.crew_id.toUpperCase()} RUN
                        </h3>
                      </div>
                      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'end', gap: '0.25rem' }}>
                        <span className={`card-badge ${getStatusBadgeClass(selectedTask.status)}`} style={{ padding: '0.4rem 1rem', fontSize: '0.85rem' }}>
                          {selectedTask.status}
                        </span>
                        <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                          {formatDate(selectedTask.created_at)}
                        </span>
                      </div>
                    </div>

                    {/* Inputs parameters card */}
                    <div className="result-section">
                      <span className="form-label" style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                        <Database size={14} /> INPUT PAYLOAD
                      </span>
                      <pre className="code-block" style={{ color: 'var(--text-primary)', backgroundColor: 'var(--bg-primary)' }}>
                        {JSON.stringify(selectedTask.inputs, null, 2)}
                      </pre>
                    </div>

                    {/* Active Monitor Status Alert */}
                    {(selectedTask.status === 'PENDING' || selectedTask.status === 'RUNNING') && (
                      <div className="card monitoring-card running" style={{ padding: '1.5rem', cursor: 'default', backgroundColor: 'rgba(59, 130, 246, 0.02)' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                          <Loader2 size={24} className="animate-spin" style={{ animation: 'spin 1.5s linear infinite', color: 'var(--accent-primary)' }} />
                          <div>
                            <h4 style={{ fontWeight: 600 }}>Executing CrewAI Agents</h4>
                            <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '0.15rem' }}>
                              FastAPI is currently running the Celery worker job. The results will populate here immediately when done.
                            </p>
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Error display */}
                    {selectedTask.error && (
                      <div className="result-section">
                        <span className="form-label" style={{ color: 'var(--accent-error)' }}>EXECUTION ERROR</span>
                        <div className="result-raw" style={{ borderColor: 'var(--accent-error)', color: 'var(--accent-error)', backgroundColor: 'rgba(239, 68, 68, 0.02)' }}>
                          {selectedTask.error}
                        </div>
                      </div>
                    )}

                    {/* Final Raw Markdown Result */}
                    {selectedTask.result?.raw && (
                      <div className="result-section">
                        <span className="form-label" style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                          <CheckCircle2 size={14} style={{ color: 'var(--accent-success)' }} /> FINAL MARKDOWN OUTPUT
                        </span>
                        <div className="result-raw">
                          {selectedTask.result.raw}
                        </div>
                      </div>
                    )}

                    {/* Dynamic Tasks outputs details */}
                    {selectedTask.result?.tasks_output && selectedTask.result.tasks_output.length > 0 && (
                      <div className="result-section" style={{ marginTop: '1.5rem' }}>
                        <span className="form-label">INDIVIDUAL AGENT TASK OUTPUTS ({selectedTask.result.tasks_output.length})</span>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', marginTop: '0.5rem' }}>
                          {selectedTask.result.tasks_output.map((out, idx) => (
                            <div key={idx} className="card" style={{ cursor: 'default', padding: '1.25rem', backgroundColor: 'var(--bg-primary)' }}>
                              <h5 style={{ fontWeight: 600, fontSize: '0.9rem', display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--accent-primary)' }}>
                                <span style={{ width: '18px', height: '18px', display: 'flex', alignItems: 'center', justify: 'center', borderRadius: '50%', backgroundColor: 'var(--bg-active)', fontSize: '0.75rem', color: 'var(--text-primary)' }}>{idx + 1}</span>
                                {out.description}
                              </h5>
                              <div style={{ fontSize: '0.85rem', color: 'var(--text-primary)', whiteSpace: 'pre-wrap', borderTop: '1px solid var(--border-color)', paddingTop: '0.75rem', marginTop: '0.5rem', lineHeight: '1.5' }}>
                                {out.raw}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Structured JSON display */}
                    {selectedTask.result?.json && (
                      <div className="result-section">
                        <span className="form-label" style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                          <Code size={14} /> STRUCTURED JSON OUTPUT
                        </span>
                        <pre className="code-block">
                          {JSON.stringify(selectedTask.result.json, null, 2)}
                        </pre>
                      </div>
                    )}

                  </div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: '1rem', padding: '4rem 0', color: 'var(--text-muted)' }}>
                    <History size={48} />
                    <p style={{ textAlign: 'center' }}>Select an execution task from the history list to review detailed logs.</p>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
