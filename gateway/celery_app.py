import os
import importlib
from celery import Celery
from gateway.database import SessionLocal, TaskRecord

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
celery_app = Celery("crew_tasks", broker=REDIS_URL, backend=REDIS_URL)

# Crew ID와 실제 모듈/클래스를 매핑하는 딕셔너리
CREW_REGISTRY = {
    "marketing": {
        "module": "crews.marketing_crew.src.marketing_crew.crew",
        "class": "MarketingCrew"
    },
    "monitoring": {
        "module": "crews.datadog_monitoring.src.datadog_monitoring.crew",
        "class": "DatadogMonitoring"
    }
}

@celery_app.task(name="execute_crew_kickoff")
def execute_crew_kickoff(task_id: str, crew_id: str, inputs: dict):
    db = SessionLocal()
    task = db.query(TaskRecord).filter(TaskRecord.id == task_id).first()
    if not task:
        return "Task not found"

    # 상태 업데이트: RUNNING
    task.status = "RUNNING"
    db.commit()

    try:
        # 1. 레지스트리에서 Crew 정보 조회
        crew_info = CREW_REGISTRY.get(crew_id)
        if not crew_info:
            raise ValueError(f"Crew '{crew_id}' is not registered.")

        # 2. 동적 임포트 (Dynamic Import)
        module = importlib.import_module(crew_info["module"])
        crew_class = getattr(module, crew_info["class"])
        
        # 3. Crew 인스턴스화 및 실행 (Kickoff)
        crew_instance = crew_class().crew()
        kickoff_result = crew_instance.kickoff(inputs=inputs)

        # 4. 결과 저장
        result_data = {
            "raw": str(kickoff_result),
            "json": kickoff_result.json_dict if hasattr(kickoff_result, 'json_dict') else None,
            "tasks_output": [
                {
                    "description": getattr(task_out, 'description', ''),
                    "raw": getattr(task_out, 'raw', str(task_out)),
                    "summary": getattr(task_out, 'summary', '')
                } for task_out in getattr(kickoff_result, 'tasks_output', [])
            ]
        }

        task.status = "SUCCESS"
        task.result = result_data
        
    except Exception as e:
        task.status = "FAILED"
        task.error = str(e)
        print(e)
    finally:
        db.commit()
        db.close()
