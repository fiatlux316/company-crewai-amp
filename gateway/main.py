import os
import json
import tempfile
from fastmcp import Client
from fastmcp.exceptions import ToolError
from fastapi import FastAPI, Depends, HTTPException, Security, status, File, UploadFile
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from gateway.database import SessionLocal, TaskRecord
from gateway.celery_app import execute_crew_kickoff, get_crew_info
from gateway.deploy_api import router as deploy_router
from gateway.upload_handler import find_main_py, extract_default_inputs
from gateway.upload_handler import process_crew_zip

app = FastAPI(title="Company Private CrewAI AMP", version="1.0.0")
app.include_router(deploy_router)

# CORS 미들웨어 등록
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer()
API_KEY = os.getenv("CREWAI_AMP_KEY", "super-secret-company-key")

def verify_api_key(credentials: HTTPAuthorizationCredentials = Security(security)):
    if credentials.credentials != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API Key"
        )
    return credentials.credentials

class KickoffRequest(BaseModel):
    inputs: dict

class DefaultInputsRequest(BaseModel):
    inputs: dict

class ScheduleRequest(BaseModel):
    enabled: bool = False
    frequency: str = "minute"
    interval: int = 1
    run_at: str | None = None
    weekdays: list[int] = []


class McpToolCallRequest(BaseModel):
    arguments: dict = {}

def _serialize_mcp_tool(tool):
    """MCP Tool 모델을 대시보드에서 사용하기 쉬운 JSON 구조로 변환합니다."""
    if hasattr(tool, "model_dump"):
        raw = tool.model_dump(by_alias=True, exclude_none=True)
    else:
        raw = {
            key: getattr(tool, key)
            for key in (
                "name", "title", "description", "inputSchema", "outputSchema",
                "annotations", "execution", "meta"
            )
            if getattr(tool, key, None) is not None
        }

    annotations = raw.get("annotations") or {}
    return {
        "name": raw.get("name", ""),
        "title": raw.get("title") or annotations.get("title") or raw.get("name", ""),
        "description": raw.get("description") or "",
        "input_schema": raw.get("inputSchema") or raw.get("input_schema") or {},
        "output_schema": raw.get("outputSchema") or raw.get("output_schema") or {},
        "annotations": annotations,
        "execution": raw.get("execution") or {},
        "meta": raw.get("_meta") or raw.get("meta") or {},
    }


@app.get("/api/v1/mcp/tools")
async def list_mcp_tools(token: str = Depends(verify_api_key)):
    """공유 MCP 서버가 현재 노출하는 모든 도구와 JSON Schema를 반환합니다."""
    server_url = os.getenv("SHARED_MCP_SERVER_URL", "http://worker:8012/sse")

    try:
        client = Client(server_url)
        async with client:
            tools = await client.list_tools()
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Failed to load tools from the shared MCP server: {e}",
        ) from e

    serialized_tools = sorted(
        (_serialize_mcp_tool(tool) for tool in tools),
        key=lambda item: item["name"].lower(),
    )
    return {
        "server": "Shared DevOps Monitoring MCP Server",
        "transport": "SSE",
        "count": len(serialized_tools),
        "tools": serialized_tools,
    }


@app.post("/api/v1/mcp/tools/{tool_name}/call")
async def call_mcp_tool(
    tool_name: str,
    payload: McpToolCallRequest,
    token: str = Depends(verify_api_key),
):
    """공유 MCP 서버에 등록된 특정 도구를 실제로 호출하여 테스트합니다."""
    server_url = os.getenv("SHARED_MCP_SERVER_URL", "http://worker:8012/sse")

    try:
        client = Client(server_url)
        async with client:
            result = await client.call_tool(tool_name, payload.arguments)
    except ToolError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Tool '{tool_name}' execution failed: {e}",
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Failed to call tool '{tool_name}' on the shared MCP server: {e}",
        ) from e

    content_texts = [
        getattr(block, "text", str(block)) for block in getattr(result, "content", [])
    ]

    return {
        "tool": tool_name,
        "arguments": payload.arguments,
        "data": getattr(result, "data", None),
        "content": content_texts,
    }


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
                    
            schedule = {}
            schedule_path = os.path.join(crew_path, "schedule.json")
            if os.path.isfile(schedule_path):
                try:
                    with open(schedule_path, 'r', encoding='utf-8') as f:
                        schedule = json.load(f)
                except (OSError, json.JSONDecodeError):
                    pass

            metadata = {}
            metadata_path = os.path.join(crew_path, "metadata.json")
            if os.path.isfile(metadata_path):
                try:
                    with open(metadata_path, 'r', encoding='utf-8') as f:
                        metadata = json.load(f)
                except (OSError, json.JSONDecodeError):
                    pass

            crews.append({
                "crew_id": item,
                "display_name": " ".join(x.capitalize() for x in item.split("_")),
                "path": f"crews/{item}",
                "default_inputs": default_inputs,
                "schedule": schedule,
                "metadata": metadata,
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

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    default_inputs_path = os.path.join(base_dir, "crews", crew_info["crew_id"], "default_inputs.json")
    default_inputs = {}
    if os.path.isfile(default_inputs_path):
        try:
            with open(default_inputs_path, 'r', encoding='utf-8') as f:
                loaded_inputs = json.load(f)
                if isinstance(loaded_inputs, dict):
                    default_inputs = loaded_inputs
        except (OSError, json.JSONDecodeError):
            pass

    # 기본값을 먼저 넣고 화면에서 전달된 값으로 덮어써 화면 입력을 우선한다.
    effective_inputs = {**default_inputs, **payload.inputs}

    db = SessionLocal()
    new_task = TaskRecord(crew_id=crew_info["crew_id"], inputs=effective_inputs)
    db.add(new_task)
    db.commit()
    db.refresh(new_task)
    
    execute_crew_kickoff.delay(new_task.id, crew_info["crew_id"], effective_inputs)
    db.close()
    
    return {
        "task_id": new_task.id,
        "status": new_task.status,
        "message": "Crew kickoff initiated. Check status using the task endpoint."
    }

# 5. Crew 기본 입력값 저장 API
@app.put("/api/v1/crews/{crew_id}/default-inputs", status_code=200)
def update_default_inputs(
    crew_id: str,
    payload: DefaultInputsRequest,
    token: str = Depends(verify_api_key)
):
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    crew_path = os.path.join(base_dir, "crews", crew_id)

    if not os.path.isdir(crew_path) or crew_id.startswith((".", "_")):
        raise HTTPException(status_code=404, detail=f"Crew '{crew_id}' not found under crews/ folder.")

    inputs_path = os.path.join(crew_path, "default_inputs.json")
    try:
        with open(inputs_path, 'w', encoding='utf-8') as f:
            json.dump(payload.inputs, f, ensure_ascii=False, indent=2)
        return {
            "message": f"Default inputs for crew '{crew_id}' have been saved successfully.",
            "default_inputs": payload.inputs
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save default inputs: {str(e)}"
        )

# 6. Crew 실행 스케줄 저장 API
@app.put("/api/v1/crews/{crew_id}/schedule", status_code=200)
def update_schedule(
    crew_id: str,
    payload: ScheduleRequest,
    token: str = Depends(verify_api_key)
):
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    crew_path = os.path.join(base_dir, "crews", crew_id)
    if not os.path.isdir(crew_path) or crew_id.startswith((".", "_")):
        raise HTTPException(status_code=404, detail=f"Crew '{crew_id}' not found under crews/ folder.")
    if payload.frequency not in {"minute", "hour", "date", "weekday"}:
        raise HTTPException(status_code=400, detail="frequency must be minute, hour, date, or weekday")
    max_interval = 24 if payload.frequency == "hour" else 1440
    if payload.frequency in {"minute", "hour"} and not 1 <= payload.interval <= max_interval:
        raise HTTPException(status_code=400, detail=f"interval must be between 1 and {max_interval}")
    if payload.enabled and payload.frequency == "date" and not payload.run_at:
        raise HTTPException(status_code=400, detail="run_at is required for date schedules")
    if payload.frequency == "weekday":
        if payload.enabled and (not payload.weekdays or any(day < 0 or day > 6 for day in payload.weekdays)):
            raise HTTPException(status_code=400, detail="weekdays must contain values from 0 to 6")
        if payload.enabled and not payload.run_at:
            raise HTTPException(status_code=400, detail="run_at is required for weekday schedules")

    schedule = payload.model_dump()
    schedule["last_run_at"] = None
    schedule_path = os.path.join(crew_path, "schedule.json")
    try:
        with open(schedule_path, 'w', encoding='utf-8') as f:
            json.dump(schedule, f, ensure_ascii=False, indent=2)
        return {"message": f"Schedule for crew '{crew_id}' saved successfully.", "schedule": schedule}
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Failed to save schedule: {str(e)}")

# 6. 태스크 상세 결과 및 상태 조회
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

# 6. 태스크 실행 이력 삭제 API (DB 로그 제거)
@app.delete("/api/v1/tasks/{task_id}", status_code=200)
def delete_task(task_id: str, token: str = Depends(verify_api_key)):
    db = SessionLocal()
    task = db.query(TaskRecord).filter(TaskRecord.id == task_id).first()
    if not task:
        db.close()
        raise HTTPException(status_code=404, detail="Task record not found.")
        
    try:
        db.delete(task)
        db.commit()
        db.close()
        return {
            "message": f"Task record '{task_id}' has been deleted successfully."
        }
    except Exception as e:
        db.close()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete task record: {str(e)}"
        )

# 7. Crew 삭제 API (소스 디렉토리 영구 제거)
@app.delete("/api/v1/crews/{crew_id}", status_code=200)
def delete_crew(
    crew_id: str,
    token: str = Depends(verify_api_key)
):
    import shutil
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    crews_dir = os.path.join(base_dir, "crews")
    
    if not os.path.exists(crews_dir):
        raise HTTPException(status_code=404, detail="crews directory not found.")
        
    matched_folder = None
    for item in os.listdir(crews_dir):
        if os.path.isdir(os.path.join(crews_dir, item)) and not item.startswith((".", "_")):
            if item == crew_id or item.replace("_crew", "") == crew_id or crew_id.replace("_crew", "") == item:
                matched_folder = item
                break
                
    if not matched_folder:
        raise HTTPException(status_code=404, detail=f"Crew '{crew_id}' not found under crews/ folder.")
        
    target_path = os.path.join(crews_dir, matched_folder)
    try:
        shutil.rmtree(target_path)
        return {
            "message": f"Crew '{crew_id}' has been deleted successfully."
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete crew folder on host: {str(e)}"
        )

# 7. React SPA 정적 파일 서빙 및 폴백 라우팅
image_dir = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), "dashboard/img"))
os.makedirs(image_dir, exist_ok=True)
app.mount("/img", StaticFiles(directory=image_dir), name="crew-profile-images")

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
