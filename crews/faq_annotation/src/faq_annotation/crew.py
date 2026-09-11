from crewai import Agent, Crew, Process, Task
from crewai.agents.agent_builder.base_agent import BaseAgent
from crewai.project import CrewBase, agent, crew, task

from .devx_llm_wrapper import llm


@CrewBase
class FaqAnnotation:
    agents: list[BaseAgent]
    tasks: list[Task]

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    @agent
    def faq_data_annotator(self) -> Agent:
        return Agent(
            config=self.agents_config["faq_data_annotator"],  # type: ignore[index]
            llm=llm,
        )

    @task
    def faq_data_annotation(self) -> Task:
        return Task(
            config=self.tasks_config["faq_data_annotation"],  # type: ignore[index]
        )

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
            cache=False,
        )
