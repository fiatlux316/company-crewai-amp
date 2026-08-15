import time

class MockTaskOutput:
    def __init__(self, description, raw, summary=""):
        self.description = description
        self.raw = raw
        self.summary = summary

class MockCrewOutput:
    def __init__(self, raw, json_dict=None, tasks_output=None):
        self.raw = raw
        self.json_dict = json_dict or {}
        self.tasks_output = tasks_output or []
        
    def __str__(self):
        return self.raw

class MockCrew:
    def kickoff(self, inputs):
        time.sleep(3)
        raw_result = f"AST Mock result for topic: {inputs.get('topic')}"
        return MockCrewOutput(raw=raw_result, json_dict=inputs)

class AstMockCrew:
    def crew(self):
        return MockCrew()
