import os
import tempfile
from fastapi import APIRouter, Depends, HTTPException, Security, status, File, UploadFile
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from gateway.upload_handler import process_crew_zip

router = APIRouter()
security = HTTPBearer()
API_KEY = os.getenv("CREWAI_API_KEY", "super-secret-company-key")

def verify_api_key(credentials: HTTPAuthorizationCredentials = Security(security)):

    print(f'credentials.credentials : {credentials.credentials}')
    print(f'API_KEY : {API_KEY}')
    if credentials.credentials != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API Key"
        )
    return credentials.credentials

# CLI 배포 등록 API 엔드포인트
@router.post("/api/v1/crews/deploy", status_code=201)
async def deploy_crew(
    overwrite: bool = False,
    file: UploadFile = File(...),
    token: str = Depends(verify_api_key)
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
        return {
            "message": f"Crew '{result['crew_id']}' has been deployed successfully via CLI API.",
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
            detail=f"Failed to process and deploy crew: {str(e)}"
        )
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
