import React, { useState, useEffect } from 'react';
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
  ChevronRight,
  Database,
  Code,
  UploadCloud,
  FileCheck,
  Trash2
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

  const [activeTab, setActiveTab] = useState('crews'); // 'crews' | 'history' | 'upload'
  const [selectedCrew, setSelectedCrew] = useState(null);
  const [inputsJson, setInputsJson] = useState('{\n  "topic": "SaaS Marketing"\n}');

  const [selectedTask, setSelectedTask] = useState(null);
  const [isExecuting, setIsExecuting] = useState(false);
  const [pollingTaskId, setPollingTaskId] = useState(null);
  const [errorMsg, setErrorMsg] = useState('');

  // 업로드 관련 상태
  const [uploadFile, setUploadFile] = useState(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadSuccess, setUploadSuccess] = useState(false);
  const [registeredCrewInfo, setRegisteredCrewInfo] = useState(null);
  
  // 업로드 진행률 및 중복 확인 모달 상태 추가
  const [uploadProgress, setUploadProgress] = useState(0);
  const [showConfirmModal, setShowConfirmModal] = useState(false);
  const [pendingFile, setPendingFile] = useState(null);

  // 삭제 관련 상태 추가
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [crewToDelete, setCrewToDelete] = useState(null);
  const [isDeleting, setIsDeleting] = useState(false);

  // 실행 이력 삭제 관련 상태 추가
  const [showDeleteTaskModal, setShowDeleteTaskModal] = useState(false);
  const [taskToDelete, setTaskToDelete] = useState(null);
  const [isDeletingTask, setIsDeletingTask] = useState(false);

  const sanitizeCrewId = (name) => {
    return name.replace(/-/g, '_').replace(/[^a-zA-Z0-9_]/g, '').toLowerCase();
  };

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
      'Authorization': `Bearer ${apiKey}`,
      ...options.headers,
    };

    // Content-Type 은 Multipart 의 경우 브라우저가 자동 boundary 설정하므로 제외 가능하도록 설계
    if (!(options.body instanceof FormData) && !headers['Content-Type']) {
      headers['Content-Type'] = 'application/json';
    }

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
      // 첫 로드 또는 에이전트 목록이 갱신되었을 때 선택 처리
      if (data.length > 0) {
        // 이미 선택된 crew가 리스트에 없다면 첫 번째로 변경
        const stillExists = data.find(c => c.crew_id === selectedCrew?.crew_id);
        if (!stillExists) {
          setSelectedCrew(data[0]);
        }
      } else {
        setSelectedCrew(null);
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

  // 5. 선택된 Crew 변경 시, 해당 에이전트의 default_inputs 자동 인출 주입
  useEffect(() => {
    if (selectedCrew) {
      const defaultInputs = selectedCrew.default_inputs || {};
      // 빈 딕셔너리면 기본 예시 형식 제공
      if (Object.keys(defaultInputs).length === 0) {
        setInputsJson('{\n  "topic": "SaaS Marketing"\n}');
      } else {
        setInputsJson(JSON.stringify(defaultInputs, null, 2));
      }
    }
  }, [selectedCrew]);

  // 6. 비동기 작업 폴링 루프 (Polling Mechanism)
  useEffect(() => {
    let intervalId = null;

    if (pollingTaskId) {
      intervalId = setInterval(async () => {
        try {
          const task = await fetchWithAuth(`/api/v1/tasks/${pollingTaskId}`);
          setSelectedTask(task);

          if (task.status === 'SUCCESS' || task.status === 'FAILED') {
            setPollingTaskId(null);
            setIsExecuting(false);
            loadTasks();
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

  // 7. Crew 실행 요청 (Trigger execution)
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

      setPollingTaskId(result.task_id);

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

  // 8. ZIP 파일 업로드 및 에이전트 등록 요청 (중복 검사 및 진행률 추적 XHR 적용)
  const handleUploadSubmit = (e) => {
    e.preventDefault();
    const file = uploadFile || pendingFile;
    if (!file) return;

    setErrorMsg('');
    setUploadSuccess(false);
    setRegisteredCrewInfo(null);

    // ZIP 파일명 기준 sanitized crew_id 계산
    const baseName = file.name.replace(/\.zip$/i, '');
    const targetCrewId = sanitizeCrewId(baseName);

    // 중복 체크: 이미 동일한 crew_id가 존재하는지 검사
    const isDuplicate = crews.some(c => c.crew_id === targetCrewId);

    if (isDuplicate && !showConfirmModal) {
      // 중복이면서 모달을 띄우지 않은 상태라면 모달 띄우기
      setPendingFile(file);
      setShowConfirmModal(true);
    } else {
      // 중복이 아니거나 모달에서 덮어쓰기 승인(Yes)된 경우
      setShowConfirmModal(false);
      performUpload(file, isDuplicate);
    }
  };

  const performUpload = (file, overwrite) => {
    setIsUploading(true);
    setUploadProgress(0);

    const xhr = new XMLHttpRequest();
    const url = `${apiEndpoint.replace(/\/$/, '')}/api/v1/crews/upload?overwrite=${overwrite}`;
    
    xhr.open('POST', url, true);
    xhr.setRequestHeader('Authorization', `Bearer ${apiKey}`);
    
    // 업로드 실시간 진행률 갱신
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) {
        const percent = Math.round((event.loaded / event.total) * 100);
        setUploadProgress(percent);
      }
    };
    
    xhr.onload = async () => {
      setIsUploading(false);
      setPendingFile(null);
      setUploadFile(null);
      
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          const response = JSON.parse(xhr.responseText);
          setUploadSuccess(true);
          setRegisteredCrewInfo(response.crew);
          await loadCrews(); // 리스트 새로고침
        } catch (e) {
          setErrorMsg('Failed to parse upload response.');
        }
      } else {
        try {
          const errRes = JSON.parse(xhr.responseText);
          setErrorMsg(errRes.detail || `Upload failed with status ${xhr.status}`);
        } catch (e) {
          setErrorMsg(`Upload failed with status ${xhr.status}`);
        }
        setUploadProgress(0);
      }
    };
    
    xhr.onerror = () => {
      setIsUploading(false);
      setPendingFile(null);
      setErrorMsg('Network error occurred during file upload.');
      setUploadProgress(0);
    };
    
    const formData = new FormData();
    formData.append('file', file);
    xhr.send(formData);
  };

  // 에이전트 삭제 요청 수행
  const handleDeleteCrew = async () => {
    if (!crewToDelete) return;
    setErrorMsg('');
    setIsDeleting(true);

    try {
      await fetchWithAuth(`/api/v1/crews/${crewToDelete.crew_id}`, {
        method: 'DELETE',
      });
      
      // 상태 초기화 및 목록 갱신
      setShowDeleteModal(false);
      setCrewToDelete(null);
      await loadCrews();
    } catch (e) {
      console.error(e);
      setErrorMsg(`Failed to delete crew: ${e.message}`);
    } finally {
      setIsDeleting(false);
    }
  };

  // 태스크 실행 이력 삭제 요청 수행
  const handleDeleteTask = async () => {
    if (!taskToDelete) return;
    setErrorMsg('');
    setIsDeletingTask(true);

    try {
      await fetchWithAuth(`/api/v1/tasks/${taskToDelete.id}`, {
        method: 'DELETE',
      });
      
      // 상태 초기화 및 목록 갱신
      setShowDeleteTaskModal(false);
      if (selectedTask?.id === taskToDelete.id) {
        setSelectedTask(null);
      }
      setTaskToDelete(null);
      await loadTasks();
    } catch (e) {
      console.error(e);
      setErrorMsg(`Failed to delete task record: ${e.message}`);
    } finally {
      setIsDeletingTask(false);
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

        <li
          className={`nav-item ${activeTab === 'upload' ? 'active' : ''}`}
          onClick={() => {
            setActiveTab('upload');
            setUploadSuccess(false);
            setRegisteredCrewInfo(null);
          }}
        >
          <UploadCloud size={18} />
          <span>Register Crew</span>
        </li>

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
              loadTasks();
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


        {/* 1. ZIP UPLOAD TAB */}
        {activeTab === 'upload' && (
          <div>
            <div className="content-header">
              <div>
                <h2 className="header-title">Register Crew</h2>
                <p className="header-subtitle">Upload a *.zip packed CrewAI application to register it automatically.</p>
              </div>
            </div>

            <div style={{ maxWidth: '680px', margin: '0 auto' }}>
              <div className="panel">
                <h3 className="panel-title">
                  <UploadCloud size={20} style={{ color: 'var(--accent-primary)' }} />
                  Upload Crew Package (.zip)
                </h3>

                <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                  CrewAI 프로젝트 루트 폴더 혹은 내부 소스파일들을 `.zip` 압축파일로 선택하여 업로드해 주세요.
                  서버에서 압축 해제 후 `main.py` 파일의 실행 파라미터(`inputs`) 설정값을 자동으로 파싱 및 등록 처리합니다.
                </p>

                <form onSubmit={handleUploadSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem', marginTop: '1rem' }}>
                  <div
                    style={{
                      border: '2px dashed var(--border-color)',
                      borderRadius: '12px',
                      padding: '3rem 2rem',
                      textAlign: 'center',
                      backgroundColor: 'var(--bg-primary)',
                      cursor: 'pointer',
                      transition: 'var(--transition-smooth)'
                    }}
                    onDragOver={(e) => e.preventDefault()}
                    onDrop={(e) => {
                      e.preventDefault();
                      if (e.dataTransfer.files && e.dataTransfer.files[0]) {
                        setUploadFile(e.dataTransfer.files[0]);
                      }
                    }}
                    onClick={() => document.getElementById('zip-file-input').click()}
                  >
                    <UploadCloud size={48} style={{ color: uploadFile ? 'var(--accent-success)' : 'var(--text-muted)', margin: '0 auto 1rem' }} />
                    <input
                      type="file"
                      id="zip-file-input"
                      accept=".zip"
                      style={{ display: 'none' }}
                      onChange={(e) => {
                        if (e.target.files && e.target.files[0]) {
                          setUploadFile(e.target.files[0]);
                        }
                      }}
                    />
                    {uploadFile ? (
                      <div>
                        <p style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{uploadFile.name}</p>
                        <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
                          {(uploadFile.size / 1024 / 1024).toFixed(2)} MB
                        </p>
                      </div>
                    ) : (
                      <div>
                        <p style={{ fontWeight: 500 }}>Drag and drop your ZIP file here, or click to browse</p>
                        <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>Only .zip archives are supported</p>
                      </div>
                    )}
                  </div>

                  <button
                    type="submit"
                    className="btn btn-primary"
                    disabled={!uploadFile || isUploading}
                    style={{ height: '46px' }}
                  >
                    {isUploading ? (
                      <>
                        <Loader2 size={16} className="animate-spin" style={{ animation: 'spin 1.5s linear infinite' }} />
                        <span>Registering & Parsing Crew... {uploadProgress}%</span>
                      </>
                    ) : (
                      <span>Register Crew Application</span>
                    )}
                  </button>

                  {isUploading && (
                    <div style={{ marginTop: '1rem' }}>
                      <div className="progress-container">
                        <div className="progress-bar" style={{ width: `${uploadProgress}%` }}></div>
                      </div>
                      <div className="progress-text">
                        <span>Uploading ZIP archive...</span>
                        <span>{uploadProgress}%</span>
                      </div>
                    </div>
                  )}
                </form>

                {/* 등록 성공 상세 정보 모달 피드백 */}
                {uploadSuccess && registeredCrewInfo && (
                  <div
                    style={{
                      marginTop: '2rem',
                      padding: '1.5rem',
                      backgroundColor: 'rgba(16, 185, 129, 0.04)',
                      border: '1px solid var(--accent-success)',
                      borderRadius: '8px',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '1rem'
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--accent-success)', fontWeight: 600 }}>
                      <FileCheck size={18} />
                      <span>Registration Completed!</span>
                    </div>

                    <div style={{ fontSize: '0.85rem' }}>
                      <p><strong>Crew Name:</strong> {registeredCrewInfo.display_name}</p>
                      <p style={{ marginTop: '0.25rem' }}><strong>Crew ID:</strong> <code style={{ fontFamily: 'var(--font-mono)' }}>{registeredCrewInfo.crew_id}</code></p>

                      <div style={{ marginTop: '1rem' }}>
                        <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-secondary)' }}>Parsed default inputs from main.py:</span>
                        <pre className="code-block" style={{ marginTop: '0.25rem', backgroundColor: 'var(--bg-primary)' }}>
                          {JSON.stringify(registeredCrewInfo.default_inputs, null, 2)}
                        </pre>
                      </div>
                    </div>

                    <button
                      className="btn btn-secondary"
                      style={{ alignSelf: 'start', borderColor: 'var(--accent-success)', color: 'var(--accent-success)' }}
                      onClick={() => {
                        // 새로 업로드한 Crew를 자동 선택하고 Executer 탭으로 이동
                        const newlyRegistered = crews.find(c => c.crew_id === registeredCrewInfo.crew_id);
                        if (newlyRegistered) {
                          setSelectedCrew(newlyRegistered);
                        } else {
                          loadCrews().then(() => {
                            const refetched = crews.find(c => c.crew_id === registeredCrewInfo.crew_id);
                            if (refetched) setSelectedCrew(refetched);
                          });
                        }
                        setActiveTab('crews');
                      }}
                    >
                      Go to Executer & Run
                    </button>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* 2. CREWS EXECUTER TAB */}
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
                      No crews found. Register a new crew using the upload menu!
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
                    <label className="form-label">INPUT VARIABLES (JSON - Parsed from main.py)</label>
                    <textarea
                      className="textarea-field"
                      value={inputsJson}
                      onChange={(e) => setInputsJson(e.target.value)}
                      placeholder='{ "topic": "SaaS Marketing" }'
                    />
                  </div>

                  <div style={{ display: 'flex', gap: '0.75rem', marginTop: '0.5rem' }}>
                    <button
                      className="btn btn-primary"
                      onClick={handleKickoff}
                      disabled={isExecuting}
                      style={{ flex: 1, height: '46px' }}
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
                    <button
                      className="btn btn-secondary"
                      onClick={() => {
                        setCrewToDelete(selectedCrew);
                        setShowDeleteModal(true);
                      }}
                      style={{ 
                        color: 'var(--accent-error)', 
                        borderColor: 'rgba(239, 68, 68, 0.3)', 
                        width: '46px', 
                        height: '46px',
                        padding: 0,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center'
                      }}
                      title="Delete Crew"
                    >
                      <Trash2 size={18} />
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}



        {/* 3. HISTORY & DETAILED VIEW TAB */}
        {activeTab === 'history' && (
          <div>
            <div className="content-header">
              <div>
                <h2 className="header-title">Run History & Control</h2>
                <p className="header-subtitle">Monitor real-time task statuses and review historical LLM execution outputs.</p>
              </div>
            </div>

            <div className="execution-container" style={{ gridTemplateColumns: '380px 1fr', alignItems: 'flex-start' }}>
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
                    <div style={{ display: 'flex', justifySpace: 'between', alignItems: 'center' }}>
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
                          backgroundColor: selectedTask?.id === task.id ? 'var(--bg-tertiary)' : 'var(--bg-secondary)',
                          // 카드 크기(높이) 고정 및 레이아웃 유지 설정
                          height: '82px',
                          minHeight: '82px',
                          flexShrink: 0,
                          display: 'flex',
                          flexDirection: 'column',
                          justifyContent: 'center',
                          position: 'relative'
                        }}
                        onClick={() => setSelectedTask(task)}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <span style={{ fontWeight: 600, fontSize: '0.9rem' }}>
                            {task.crew_id}
                          </span>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                            {/* 선택된 카드의 우측 상태 배지 왼쪽에 컴팩트 삭제 버튼 배치 */}
                            {selectedTask?.id === task.id && (
                              <button
                                onClick={(e) => {
                                  e.stopPropagation(); // 카드 선택 클릭 방지
                                  setTaskToDelete(task);
                                  setShowDeleteTaskModal(true);
                                }}
                                style={{
                                  background: 'none',
                                  border: 'none',
                                  color: 'var(--accent-error)',
                                  cursor: 'pointer',
                                  padding: '2px',
                                  display: 'flex',
                                  alignItems: 'center',
                                  transition: 'var(--transition-smooth)'
                                }}
                                title="Delete task record"
                              >
                                <Trash2 size={14} />
                              </button>
                            )}
                            <span className={`card-badge ${getStatusBadgeClass(task.status)}`}>
                              {task.status}
                            </span>
                          </div>
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

      {/* OVERWRITE CONFIRMATION MODAL */}
      {showConfirmModal && pendingFile && (
        <div className="modal-overlay">
          <div className="modal-content">
            <div className="modal-header" style={{ color: 'var(--accent-warning)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Settings size={20} />
              <span>중복된 에이전트 경고</span>
            </div>
            <div className="modal-body">
              <p>
                동일한 ID인 <strong>{sanitizeCrewId(pendingFile.name.replace(/\.zip$/i, ''))}</strong> 에이전트가 서버에 이미 존재합니다.
              </p>
              <p style={{ marginTop: '0.65rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                기존 소스코드를 삭제하고 덮어쓸까요?
              </p>
            </div>
            <div className="modal-actions">
              <button 
                className="btn btn-secondary" 
                onClick={() => {
                  setShowConfirmModal(false);
                  setPendingFile(null);
                  setUploadFile(null);
                }}
              >
                아니오, 취소
              </button>
              <button 
                className="btn btn-primary" 
                style={{ backgroundColor: 'var(--accent-warning)', color: '#000' }}
                onClick={() => {
                  setShowConfirmModal(false);
                  performUpload(pendingFile, true);
                }}
              >
                예, 덮어쓰기
              </button>
            </div>
          </div>
        </div>
      )}

      {/* DELETE CONFIRMATION MODAL */}
      {showDeleteModal && crewToDelete && (
        <div className="modal-overlay">
          <div className="modal-content">
            <div className="modal-header" style={{ color: 'var(--accent-error)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Trash2 size={20} />
              <span>에이전트 삭제 경고</span>
            </div>
            <div className="modal-body">
              <p>
                선택하신 <strong>{crewToDelete.display_name}</strong> 에이전트를 서버에서 완전히 삭제하시겠습니까?
              </p>
              <p style={{ marginTop: '0.65rem', fontWeight: 600, color: 'var(--accent-error)' }}>
                진짜 삭제하시겠습니까? (이 작업은 되돌릴 수 없으며 소스 폴더에서도 영구 삭제됩니다)
              </p>
            </div>
            <div className="modal-actions">
              <button 
                className="btn btn-secondary" 
                onClick={() => {
                  setShowDeleteModal(false);
                  setCrewToDelete(null);
                }}
                disabled={isDeleting}
              >
                아니오, 취소
              </button>
              <button 
                className="btn btn-primary" 
                style={{ backgroundColor: 'var(--accent-error)', color: '#fff' }}
                onClick={handleDeleteCrew}
                disabled={isDeleting}
              >
                {isDeleting ? '삭제 중...' : '예, 삭제합니다'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* DELETE TASK RECORD CONFIRMATION MODAL */}
      {showDeleteTaskModal && taskToDelete && (
        <div className="modal-overlay">
          <div className="modal-content">
            <div className="modal-header" style={{ color: 'var(--accent-error)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Trash2 size={20} />
              <span>실행 이력 삭제</span>
            </div>
            <div className="modal-body">
              <p>
                ID가 <strong>{taskToDelete.id.substring(0, 8)}...</strong>인 <strong>{taskToDelete.crew_id}</strong> 실행 이력을 삭제하시겠습니까?
              </p>
              <p style={{ marginTop: '0.65rem', fontWeight: 600, color: 'var(--accent-error)' }}>
                진짜 삭제하시겠습니까? (이 작업은 되돌릴 수 없으며 데이터베이스에서 영구 제거됩니다)
              </p>
            </div>
            <div className="modal-actions">
              <button 
                className="btn btn-secondary" 
                onClick={() => {
                  setShowDeleteTaskModal(false);
                  setTaskToDelete(null);
                }}
                disabled={isDeletingTask}
              >
                아니오, 취소
              </button>
              <button 
                className="btn btn-primary" 
                style={{ backgroundColor: 'var(--accent-error)', color: '#fff' }}
                onClick={handleDeleteTask}
                disabled={isDeletingTask}
              >
                {isDeletingTask ? '삭제 중...' : '예, 삭제합니다'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
