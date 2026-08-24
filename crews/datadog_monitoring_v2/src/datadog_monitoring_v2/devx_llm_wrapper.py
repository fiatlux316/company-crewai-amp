import os
import requests
from typing import Any, Dict, List, Optional, Union
from dotenv import load_dotenv
from pydantic import Field
from crewai.llms.base_llm import BaseLLM
from crewai.utilities.types import LLMMessage
from crewai.llms.providers.bedrock.completion import BedrockCompletion
from crewai.llms.providers.gemini.completion import GeminiCompletion

# .env 파일 로드
load_dotenv()

class CompanyLLMWrapper(BaseLLM):
    """
    회사 내부 생성형 AI 게이트웨이 호출을 위한 Custom CrewAI LLM Wrapper
    """
    api_url: str 
    api_key: str 
    
    # BaseLLM의 필드 오버라이드
    llm_type: str 
    model: str 

    def __init__(self, **data: Any):
        # 환경변수 로드를 위해 __init__ 시점의 os.getenv 우선 적용 (BaseModel의 before 검증 통과용)
        if "model" not in data or not data["model"]:
            data["model"] = os.getenv("DEVX_MODEL")
        if "api_url" not in data or not data["api_url"]:
            data["api_url"] = os.getenv("DEVX_API_URL")
        if "api_key" not in data or not data["api_key"]:
            data["api_key"] = os.getenv("DEVX_API_KEY")
        if "llm_type" not in data or not data["llm_type"]:
            data["llm_type"] = os.getenv("LLM_TYPE")
        if "temperature" not in data or data["temperature"] is None:
            temp_env = os.getenv("DEVX_TEMPERATURE")
            data["temperature"] = float(temp_env) if temp_env is not None else 0.0
            
        super().__init__(**data)

    def call(
        self,
        messages: Union[str, List[LLMMessage]],
        tools: Optional[List[Dict[str, Any]]] = None,
        callbacks: Optional[List[Any]] = None,
        available_functions: Optional[Dict[str, Any]] = None,
        from_task: Optional[Any] = None,
        from_agent: Optional[Any] = None,
        response_model: Optional[Any] = None,
    ) -> str:
        # 메시지 포맷 변환
        formatted_messages = []
        if isinstance(messages, str):
            formatted_messages = [{"role": "user", "content": messages}]
        else:
            for msg in messages:
                content = msg.get("content", "")
                if not isinstance(content, str):
                    content = str(content)
                formatted_messages.append({
                    "role": msg.get("role", "user"),
                    "content": content
                })

        # HTTP 헤더 설정
        headers = {
            "Content-Type": "application/json",
            "x-litellm-api-key": self.api_key
        }

        # 요청 페이로드 설정
        payload = {
            "model": self.model,
            "messages": formatted_messages,
        }

        # Bedrock 모델은 현재 이 게이트웨이에서 temperature 관련 필드를 전달하면 실패합니다.
        if self.temperature is not None and not (isinstance(self.model, str) and self.model.startswith("bedrock/")):
            payload["temperature"] = self.temperature

        try:
            # API 호출
            response = requests.post(self.api_url, headers=headers, json=payload)
            response.raise_for_status()
            response_json = response.json()
            
            # 응답 본문에서 텍스트 추출
            return response_json["choices"][0]["message"]["content"]
            
        except Exception as e:
            raise RuntimeError(f"사내 생성형 AI API 호출 오류: {e}")

# 래퍼 생성 (class 내부의 __init__에서 환경변수 로드를 처리하므로 파라미터 전달 불필요)
llm = None 
if os.getenv("LLM_TYPE") == "company-llm-gateway":
    print("사내 생성형 AI API 호출 : " + os.getenv("DEVX_MODEL"))
    llm = CompanyLLMWrapper()
elif os.getenv("LLM_TYPE") == "aws-bedrock":
    print("AWS Bedrock 호출 : " + os.getenv("BEDROCK_MODEL"))
    llm = BedrockCompletion(
        model=os.getenv("BEDROCK_MODEL"),
        region_name=os.getenv("BEDROCK_REGION"),
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        #additional_model_request_fields={"inferenceConfig": {"topK": int(os.getenv("BEDROCK_TOP_K", "1"))}}
    )
elif os.getenv("LLM_TYPE") == "gemini":
    print("Gemini 호출 : " + os.getenv("GEMINI_MODEL"))
    llm = GeminiCompletion(
        model=os.getenv("GEMINI_MODEL"),
        api_key=os.getenv("GEMINI_API_KEY"),
    )
else:
    raise ValueError("LLM_TYPE을 설정해주세요.")