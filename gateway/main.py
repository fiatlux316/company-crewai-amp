import os
from fastapi import FastAPI, Depends, HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from gateway.database import SessionLocal, TaskRecord
from gateway.celery_app import execute_crew_kickoff, CREW_REGISTRY

app = FastAPI(title="Company Private CrewAI AMP", version="1.0.0")
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

@app.post("/api/v1/crews/{crew_id}/kickoff", status_code=202)
def kickoff_crew(
    crew_id: str, 
    payload: KickoffRequest, 
    token: str = Depends(verify_api_key)
):
    if crew_id not in CREW_REGISTRY:
        raise HTTPException(status_code=404, detail=f"Crew '{crew_id}' not found.")

    db = SessionLocal()
    # 1. DB에 태스크 생성
    new_task = TaskRecord(crew_id=crew_id, inputs=payload.inputs)
    db.add(new_task)
    db.commit()
    db.refresh(new_task)
    
    # 2. Celery로 비동기 작업 위임 : REDIS 큐에 삽입
    execute_crew_kickoff.delay(new_task.id, crew_id, payload.inputs)
    
    db.close()
    return {
        "task_id": new_task.id,
        "status": new_task.status,
        "message": "Crew kickoff initiated. Check status using the task endpoint."
    }

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
