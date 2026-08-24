from crewai.tools import BaseTool
from typing import Type
from pydantic import BaseModel, Field

from .datadog_api import datadog_apm_search, datadog_logs_search
from .email_api import send_outlook_email, send_google_email

class DatadogLogsSearchInput(BaseModel):
    """Input schema for DatadogLogsSearch."""
    time_range: str = Field(..., description="분석할 타임 구간 (last 1 hour, last 6 hours, last 24 hours 등)")
    datadog_query: str = Field(..., description="datadog 질의 쿼리, inputs 에서 전달 받음")
    limit: str = Field(..., description="결과로 반환할 최대 로그 수, inputs 에서 전달 받음")
    search_option: str = Field(..., description="검색 옵션 (logs 또는 apm), inputs 에서 전달 받음")
    

class DatadogLogsSearch(BaseTool):
    name: str = "DatadogLogsSearch"
    description: str = "Datadog Logs Search tool 입니다."
    args_schema: Type[BaseModel] = DatadogLogsSearchInput

    def _run(self, time_range:str, datadog_query:str, limit:str, search_option:str) -> str:

        # custom logic to process the inputs and call the Datadog API
        limit = int(limit)  # Convert limit to integer

        if search_option == "logs":
            return datadog_logs_search(datadog_query, time_range, limit)
        elif search_option == "apm":
            return datadog_apm_search(datadog_query, time_range, limit)
        else:
            raise ValueError(f"Invalid search_option: {search_option}. Must be 'logs' or 'apm'.")   

class SendOutLookMailInput(BaseModel):
    """Input schema for SendOutLookMail."""
    subject: str = Field(..., description="메일로 발송할 보고서 제목")
    body: str = Field(..., description="마크다운 형태로 작성된 보고서 원문")
    recipient_email: str = Field(..., description="메일을 수신할 사람의 이메일 주소")
    

class SendOutLookMail(BaseTool):
    name: str = "SendOutLookMail"
    description: str = "분석한 보고서를 이메일로 발송하는 tool 입니다."
    args_schema: Type[BaseModel] = SendOutLookMailInput

    def _run(self, subject:str, body:str, recipient_email: str) -> str:

        #return send_outlook_email(subject, body, recipient_email)
        return send_google_email(subject, body, recipient_email)
