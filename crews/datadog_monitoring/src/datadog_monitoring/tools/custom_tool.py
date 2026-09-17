import os
from crewai.tools import BaseTool
from typing import Type
from pydantic import BaseModel, Field

# 사전에 작성된 외부 연동 API 및 패키지를 임포트하여 로직 구현
from .datadog_api import datadog_apm_search, datadog_logs_search
from .email_api import send_outlook_email


class SendOutLookMailInput(BaseModel):
    """Input schema for SendOutLookMail."""
    subject: str = Field(..., description="이메일 제목. 예: '애플리케이션 로그 모니터링 보고서 (now-1h)'")
    markdown_content: str = Field(..., description="이메일 본문. 마크다운 보고서 전문을 그대로 전달하면 HTML로 변환되어 발송됩니다.")
    recipient_email: str = Field(default="", description="수신자 이메일 주소. 비워두면 RECIPIENT_EMAIL 환경 변수를 사용합니다.")


class SendOutLookMail(BaseTool):
    name: str = "SendOutLookMail"
    description: str = (
        "Outlook(Office 365) SMTP로 마크다운 보고서를 HTML 이메일로 발송합니다. "
        "제목(subject), 본문(markdown_content), 수신자(recipient_email)를 전달해야 합니다. "
        "발송 계정은 OUTLOOK_EMAIL, OUTLOOK_PASSWORD 환경 변수를 사용합니다."
    )
    args_schema: Type[BaseModel] = SendOutLookMailInput

    def _run(self, subject: str, markdown_content: str, recipient_email: str = "") -> str:

        # [이부분이 핵심] 실제 로직을 처리하는 api 적용
        to_email = (recipient_email or "").strip() or os.environ.get("RECIPIENT_EMAIL", "").strip()
        if not to_email:
            return "메일 발송 실패: 수신자 주소가 없습니다. recipient_email 인자 또는 RECIPIENT_EMAIL 환경 변수를 설정하세요."

        return send_outlook_email(subject, markdown_content, to_email)


class DatadogLogsSearchInput(BaseModel):
    """Input schema for DatadogLogsSearch."""
    datadog_query: str = Field(..., description="Datadog 검색 쿼리. 예: 'service:erody-assist-service status:error'")
    time_range: str = Field(..., description="조회 시간 범위. 예: 'now-1h', 'now-24h'")
    limit: str = Field(..., description="가져올 최대 이벤트 건수. 숫자 문자열로 전달합니다. 예: '10'")
    search_option: str = Field(default="logs", description="조회 대상. 'logs'는 로그, 'apm'은 APM 트레이스, 'all'은 둘 다 조회합니다.")


class DatadogLogsSearch(BaseTool):
    name: str = "DatadogLogsSearch"
    description: str = (
        "Datadog에서 애플리케이션 로그 또는 APM 트레이스를 조회하여 원본 데이터를 반환합니다. "
        "타임스탬프, 로그 레벨, 서비스명, 메시지, 스택 트레이스가 포함됩니다. "
        "조회 결과가 없으면 '조회 결과 없음'에 해당하는 응답을 그대로 반환하므로, "
        "결과가 없을 때 데이터를 임의로 만들어내면 안 됩니다. "
        "인증은 DD_API_KEY, DD_APP_KEY, DD_SITE 환경 변수를 사용합니다."
    )
    args_schema: Type[BaseModel] = DatadogLogsSearchInput

    def _run(self, datadog_query: str, time_range: str, limit: str, search_option: str = "logs") -> str:

        # [이부분이 핵심] 실제 로직을 처리하는 api 적용
        try:
            limit = int(str(limit).strip())
        except (TypeError, ValueError):
            limit = 10

        option = str(search_option or "logs").strip().lower()

        if option in ("apm", "trace", "traces"):
            return datadog_apm_search(datadog_query, time_range, limit)

        if option in ("all", "both"):
            logs_result = datadog_logs_search(datadog_query, time_range, limit)
            apm_result = datadog_apm_search(datadog_query, time_range, limit)
            return f"===== LOGS =====\n{logs_result}\n\n===== APM =====\n{apm_result}"

        return datadog_logs_search(datadog_query, time_range, limit)
