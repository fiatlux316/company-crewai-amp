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
        # 비동기 실행 흐름을 쉽게 검증할 수 있도록 5초 지연(Sleep) 발생
        time.sleep(5)
        
        topic = inputs.get("topic", "General Topic")
        raw_result = f"Successfully generated a marketing plan for '{topic}' using Company Private CrewAI AMP."
        json_data = {
            "topic": topic,
            "status": "completed",
            "generated_by": "MarketingCrew (Mock)"
        }
        tasks_output = [
            MockTaskOutput(
                description=f"Analyze trend for {topic}",
                raw=f"Trend analysis reports strong interest in {topic}."
            ),
            MockTaskOutput(
                description=f"Draft post on {topic}",
                raw=raw_result
            )
        ]
        return MockCrewOutput(raw=raw_result, json_dict=json_data, tasks_output=tasks_output)

class MarketingCrew:
    def crew(self):
        return MockCrew()
