import os
import json
import tempfile
from fastapi import FastAPI, Depends, HTTPException, Security, status, File, UploadFile
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from gateway.database import SessionLocal, TaskRecord
from gateway.celery_app import execute_crew_kickoff, get_crew_info
from gateway.upload_handler import process_crew_zip, find_main_py, extract_default_inputs

app = FastAPI(title="Company Private CrewAI AMP", version="1.0.0")

# CORS 미들웨어 등록
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer()
API_KEY = os.getenv("CREWAI_API_KEY", "super-secret-company-key")

def verify_api_key(credentials: HTTPAuthorizationCredentials = Security(security)):
    if credentials.credentials != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API Key"
        )
    return credentials.credentials

class KickoffRequest(BaseModel):
    inputs: dict

# 1. crews 폴더 동적 스캔 및 default_inputs 포함 엔드포인트
@app.get("/api/v1/crews")
def list_crews(token: str = Depends(verify_api_key)):
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    crews_dir = os.path.join(base_dir, "crews")
    
    if not os.path.exists(crews_dir):
        return []
        
    crews = []
    for item in os.listdir(crews_dir):
        if os.path.isdir(os.path.join(crews_dir, item)) and not item.startswith((".", "_")):
            crew_path = os.path.join(crews_dir, item)
            default_inputs = {}
            default_inputs_path = os.path.join(crew_path, "default_inputs.json")
            
            # default_inputs.json 파일이 없으면 main.py를 파싱하여 생성 시도 (기존 수동 추가된 소스 대응)
            if not os.path.exists(default_inputs_path):
                try:
                    main_py = find_main_py(crew_path)
                    if main_py:
                        default_inputs = extract_default_inputs(main_py)
                        # JSON 파일로 자동 캐싱 저장
                        with open(default_inputs_path, 'w', encoding='utf-8') as f:
                            json.dump(default_inputs, f, ensure_ascii=False, indent=2)
                except Exception as e:
                    print(f"Failed to auto-generate default_inputs for {item}: {e}")
            else:
                try:
                    with open(default_inputs_path, 'r', encoding='utf-8') as f:
                        default_inputs = json.load(f)
                except Exception:
                    pass
                    
            crews.append({
                "crew_id": item,
                "display_name": " ".join(x.capitalize() for x in item.split("_")),
                "path": f"crews/{item}",
                "default_inputs": default_inputs
            })
    return crews

# 2. Crew ZIP 업로드 및 등록 API
@app.post("/api/v1/crews/upload", status_code=201)
async def upload_crew(
    overwrite: bool = False,
    file: UploadFile = File(...),
    token: str = Depends(verify_api_key)
):
    if not file.filename.endswith(".zip"):
        raise HTTPException(
            status_code=400,
            detail="Only .zip files are allowed."
        )
        
    # 임시 파일 경로를 생성하고 바이트 쓰기 수행
    with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
        try:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to write uploaded file to disk: {str(e)}"
            )
            
    try:
        result = process_crew_zip(tmp_path, file.filename, overwrite=overwrite)
        return {
            "message": f"Crew '{result['crew_id']}' has been registered successfully.",
            "crew": result
        }
    except FileExistsError as e:
        raise HTTPException(
            status_code=409,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to process and register crew: {str(e)}"
        )
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

# 3. 태스크 실행 이력 조회
@app.get("/api/v1/tasks")
def list_tasks(token: str = Depends(verify_api_key)):
    db = SessionLocal()
    tasks = db.query(TaskRecord).order_by(TaskRecord.created_at.desc()).all()
    db.close()
    return tasks

# 4. 비동기 Kickoff 실행
@app.post("/api/v1/crews/{crew_id}/kickoff", status_code=202)
def kickoff_crew(
    crew_id: str, 
    payload: KickoffRequest, 
    token: str = Depends(verify_api_key)
):
    crew_info = get_crew_info(crew_id)
    if not crew_info:
        raise HTTPException(status_code=404, detail=f"Crew '{crew_id}' not found under crews/ folder.")

    db = SessionLocal()
    new_task = TaskRecord(crew_id=crew_info["crew_id"], inputs=payload.inputs)
    db.add(new_task)
    db.commit()
    db.refresh(new_task)
    
    execute_crew_kickoff.delay(new_task.id, crew_info["crew_id"], payload.inputs)
    db.close()
    
    return {
        "task_id": new_task.id,
        "status": new_task.status,
        "message": "Crew kickoff initiated. Check status using the task endpoint."
    }

# 5. 태스크 상세 결과 및 상태 조회
@app.get("/api/v1/tasks/{task_id}")
def get_task_status(task_id: str, token: str = Depends(verify_api_key)):
    db = SessionLocal()
    task = db.query(TaskRecord).filter(TaskRecord.id == task_id).first()
    db.close()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")
        
    return {
        "task_id": task.id,
        "crew_id": task.crew_id,
        "status": task.status,
        "result": task.result,
        "error": task.error,
        "created_at": task.created_at,
        "updated_at": task.updated_at
    }

# 6. React SPA 정적 파일 서빙 및 폴백 라우팅
dist_dir = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), "dashboard/dist"))
if os.path.exists(dist_dir):
    app.mount("/assets", StaticFiles(directory=os.path.join(dist_dir, "assets")), name="assets")

    @app.get("/{path_name:path}")
    async def catch_all(path_name: str):
        if path_name.startswith("api/"):
            raise HTTPException(status_code=404, detail="API endpoint not found.")
            
        file_path = os.path.join(dist_dir, path_name)
        if os.path.exists(file_path) and os.path.isfile(file_path):
            return FileResponse(file_path)
            
        return FileResponse(os.path.join(dist_dir, "index.html"))
