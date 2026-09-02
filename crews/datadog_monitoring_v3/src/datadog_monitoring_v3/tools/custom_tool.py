from crewai.tools import BaseTool
from typing import Type
from pydantic import BaseModel, Field

class DatadogLogsSearchInput(BaseModel):
    """Input schema for DatadogLogsSearch."""
    datadog_query: str = Field(..., description="datadog_query에 대한 설명을 자세하게 입력하세요.")
    time_range: str = Field(..., description="time_range에 대한 설명을 자세하게 입력하세요.")
    search_option: str = Field(..., description="search_option에 대한 설명을 자세하게 입력하세요.")
    output_path: str = Field(..., description="output_path에 대한 설명을 자세하게 입력하세요.")
    limit: str = Field(..., description="limit에 대한 설명을 자세하게 입력하세요.")
    

class DatadogLogsSearch(BaseTool):
    name: str = "DatadogLogsSearch"
    description: str = "DatadogLogsSearch에 대한 설명을 자세하게 입력하세요."
    args_schema: Type[BaseModel] = DatadogLogsSearchInput

    def _run(self, datadog_query:str, time_range:str, search_option:str, output_path:str, limit:str) -> str:
        # [TODO: Pseudo-code] 실제 비즈니스 로직을 여기에 구현하세요.
        # 예: import pandas as pd
        # df = pd.read_csv('data.csv')
        # return df[df['target'] == query].to_string()
        
        return f"[DatadogLogsSearch] 성공적으로 실행되었습니다."

class SendOutLookMailInput(BaseModel):
    """Input schema for SendOutLookMail."""
    datadog_query: str = Field(..., description="datadog_query에 대한 설명을 자세하게 입력하세요.")
    time_range: str = Field(..., description="time_range에 대한 설명을 자세하게 입력하세요.")
    search_option: str = Field(..., description="search_option에 대한 설명을 자세하게 입력하세요.")
    output_path: str = Field(..., description="output_path에 대한 설명을 자세하게 입력하세요.")
    limit: str = Field(..., description="limit에 대한 설명을 자세하게 입력하세요.")
    

class SendOutLookMail(BaseTool):
    name: str = "SendOutLookMail"
    description: str = "SendOutLookMail에 대한 설명을 자세하게 입력하세요."
    args_schema: Type[BaseModel] = SendOutLookMailInput

    def _run(self, datadog_query:str, time_range:str, search_option:str, output_path:str, limit:str) -> str:
        # [TODO: Pseudo-code] 실제 비즈니스 로직을 여기에 구현하세요.
        # 예: import pandas as pd
        # df = pd.read_csv('data.csv')
        # return df[df['target'] == query].to_string()
        
        return f"[SendOutLookMail] 성공적으로 실행되었습니다."

