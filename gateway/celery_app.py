import os
import importlib
import inspect
from celery import Celery
from gateway.database import SessionLocal, TaskRecord

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
celery_app = Celery("crew_tasks", broker=REDIS_URL, backend=REDIS_URL)

def snake_to_camel(snake_str):
    return "".join(x.capitalize() for x in snake_str.split("_"))

def get_crew_info(crew_id: str):
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    crews_dir = os.path.join(base_dir, "crews")
    
    if not os.path.exists(crews_dir):
        return None
        
    # exact match or suffix match
    matched_folder = None
    for item in os.listdir(crews_dir):
        if os.path.isdir(os.path.join(crews_dir, item)) and not item.startswith((".", "_")):
            if item == crew_id or item.replace("_crew", "") == crew_id or crew_id.replace("_crew", "") == item:
                matched_folder = item
                break
                
    if not matched_folder:
        return None
        
    actual_crew_id = matched_folder
    class_name = snake_to_camel(actual_crew_id)
    module_path = f"crews.{actual_crew_id}.src.{actual_crew_id}.crew"
    
    return {
        "module": module_path,
        "class": class_name,
        "crew_id": actual_crew_id
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
        # 1. 동적 Crew 정보 조회
        crew_info = get_crew_info(crew_id)
        if not crew_info:
            raise ValueError(f"Crew '{crew_id}' is not found under crews/ folder.")

        # 2. 동적 임포트 (Dynamic Import)
        module = importlib.import_module(crew_info["module"])
        
        # 3. 클래스 탐색 (클래스 데코레이터 상속 등으로 이름이 다를 수 있어 인스펙션 적용)
        # 외부 임포트된 클래스(예: crewai.Crew)가 오매칭되는 것을 방지하기 위해 해당 모듈 내 선언된 클래스만 필터링
        crew_class = None
        for name, obj in inspect.getmembers(module, inspect.isclass):
            if obj.__module__ == module.__name__:
                if name.endswith("Crew") or name.lower() == crew_info["crew_id"].lower() or name == crew_info["class"]:
                    crew_class = obj
                    break
                
        if not crew_class:
            crew_class = getattr(module, crew_info["class"])
            
        # 4. Crew 인스턴스화 및 실행 (Kickoff)
        crew_instance = crew_class().crew()
        kickoff_result = crew_instance.kickoff(inputs=inputs)

        # 5. 결과 저장
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
    finally:
        db.commit()
        db.close()
