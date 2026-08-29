import os
import tempfile
import json
import datetime
from fastapi import APIRouter, Depends, HTTPException, File, UploadFile
from gateway.auth import get_current_user
from gateway.upload_handler import process_crew_zip

router = APIRouter()

# CLI 배포 등록 API 엔드포인트
@router.post("/api/v1/crews/deploy", status_code=201)
async def deploy_crew(
    overwrite: bool = False,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    if not file.filename.endswith(".zip"):
        raise HTTPException(
            status_code=400,
            detail="Only .zip files are allowed."
        )
    
    # 임시 파일 생성 및 업로드 바이너리 적재
    with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
        try:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to write deploy package: {str(e)}"
            )
            
    try:
        # ZIP 분석 및 소스 적재, AST 인풋 캐싱 위임
        result = process_crew_zip(tmp_path, file.filename, overwrite=overwrite)
        crew_id = result["crew_id"]
        
        # 감사 로그를 저장할 metadata.json 경로 구성
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        crew_path = os.path.join(base_dir, "crews", crew_id)
        metadata_path = os.path.join(crew_path, "metadata.json")
        
        # M365 OIDC 클레임에서 파싱한 배포자 정보와 배포 시간 기록
        metadata = {
            "crew_id": crew_id,
            "display_name": " ".join(x.capitalize() for x in crew_id.split("_")),
            "deployed_by": {
                "email": current_user["email"],
                "name": current_user["name"],
                "employee_id": current_user["employee_id"],
                "auth_provider": "M365_EntraID"
            },
            "deployed_at": datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat()
        }
        
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
            
        print(f"[Deploy API] metadata.json successfully written for {crew_id} by {current_user['email']}")
        
        return {
            "message": f"Crew '{crew_id}' has been deployed successfully via authenticated CLI API.",
            "crew": result,
            "metadata": metadata
        }
    except FileExistsError as e:
        raise HTTPException(
            status_code=409,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to process and deploy crew: {str(e)}"
        )
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
