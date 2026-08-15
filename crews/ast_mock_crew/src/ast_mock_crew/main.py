#!/usr/bin/env python
import warnings
from ast_mock_crew.crew import AstMockCrew

def run():
    # AST 파서가 읽어들여 대시보드에 기본 값으로 표시할 inputs 사전
    inputs = {
        "topic": "AST ZIP Upload Parsing",
        "speed": "lightning_fast",
        "features": ["dynamic_scan", "ast_extract"]
    }
    AstMockCrew().crew().kickoff(inputs=inputs)
