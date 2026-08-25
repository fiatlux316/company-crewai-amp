import os
import importlib
import inspect
import json
import threading
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from celery import Celery
from gateway.database import SessionLocal, TaskRecord

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
celery_app = Celery("crew_tasks", broker=REDIS_URL, backend=REDIS_URL)
SCHEDULE_TIMEZONE = ZoneInfo("Asia/Seoul")
SCHEDULE_POLL_SECONDS = 30
_schedule_lock = threading.Lock()

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

def _crew_dir(crew_id: str):
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "crews", crew_id)

def _create_and_enqueue(crew_id: str):
    crew_path = _crew_dir(crew_id)
    inputs = {}
    inputs_path = os.path.join(crew_path, "default_inputs.json")
    if os.path.isfile(inputs_path):
        try:
            with open(inputs_path, "r", encoding="utf-8") as f:
                loaded_inputs = json.load(f)
                if isinstance(loaded_inputs, dict):
                    inputs = loaded_inputs
        except (OSError, json.JSONDecodeError):
            pass

    db = SessionLocal()
    try:
        task = TaskRecord(crew_id=crew_id, inputs=inputs)
        db.add(task)
        db.commit()
        db.refresh(task)
        execute_crew_kickoff.delay(task.id, crew_id, inputs)
    finally:
        db.close()

def _schedule_is_due(schedule, now):
    if not schedule.get("enabled"):
        return False
    frequency = schedule.get("frequency")
    last_run = schedule.get("last_run_at")
    if last_run:
        try:
            last_run_time = datetime.fromisoformat(last_run).astimezone(SCHEDULE_TIMEZONE)
        except ValueError:
            last_run_time = None
    else:
        last_run_time = None

    if frequency == "minute":
        return last_run_time is None or now - last_run_time >= timedelta(minutes=int(schedule.get("interval", 1)))
    if frequency == "hour":
        return last_run_time is None or now - last_run_time >= timedelta(hours=int(schedule.get("interval", 1)))

    run_at = schedule.get("run_at")
    if not run_at:
        return False
    try:
        scheduled_time = datetime.fromisoformat(run_at)
        if scheduled_time.tzinfo is None:
            scheduled_time = scheduled_time.replace(tzinfo=SCHEDULE_TIMEZONE)
        scheduled_time = scheduled_time.astimezone(SCHEDULE_TIMEZONE)
    except ValueError:
        return False

    if frequency == "date":
        return last_run_time is None and now >= scheduled_time
    if frequency == "weekday":
        return now.weekday() in schedule.get("weekdays", []) and now.hour == scheduled_time.hour and now.minute == scheduled_time.minute and (last_run_time is None or last_run_time.date() < now.date())
    return False

def _schedule_loop():
    print(
        f"Crew schedule runner started ({SCHEDULE_TIMEZONE.key}, "
        f"poll={SCHEDULE_POLL_SECONDS}s)",
        flush=True,
    )
    while True:
        try:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            crews_dir = os.path.join(base_dir, "crews")
            now = datetime.now(SCHEDULE_TIMEZONE).replace(second=0, microsecond=0)
            for crew_id in os.listdir(crews_dir) if os.path.isdir(crews_dir) else []:
                schedule_path = os.path.join(crews_dir, crew_id, "schedule.json")
                if not os.path.isfile(schedule_path):
                    continue
                try:
                    with open(schedule_path, "r", encoding="utf-8") as f:
                        schedule = json.load(f)
                except (OSError, json.JSONDecodeError):
                    continue
                if not _schedule_is_due(schedule, now):
                    continue
                with _schedule_lock:
                    _create_and_enqueue(crew_id)
                    schedule["last_run_at"] = now.isoformat()
                    if schedule.get("frequency") == "date":
                        schedule["enabled"] = False
                    with open(schedule_path, "w", encoding="utf-8") as f:
                        json.dump(schedule, f, ensure_ascii=False, indent=2)
                print(f"Scheduled crew enqueued: {crew_id} at {now.isoformat()}", flush=True)
        except Exception as e:
            print(f"Schedule runner error: {e}", flush=True)
        time.sleep(SCHEDULE_POLL_SECONDS)

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

        # 1-1. 해당 Crew 폴더의 .env 파일 강제 로드 (override=True)
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        crew_env_path = os.path.join(base_dir, "crews", crew_info["crew_id"], ".env")
        if os.path.exists(crew_env_path):
            load_dotenv(dotenv_path=crew_env_path, override=True)

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

if os.getenv("SCHEDULE_RUNNER_ENABLED", "false").lower() == "true":
    threading.Thread(target=_schedule_loop, daemon=True, name="crew-schedule-runner").start()
else:
    print("Crew schedule runner disabled", flush=True)
