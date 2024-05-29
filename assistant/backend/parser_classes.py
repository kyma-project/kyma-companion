from langchain.pydantic_v1 import BaseModel, Field


class CommandResponse(BaseModel):
    resources: list[str] = Field(description="The set of kubectl commands one should execute to request kubernetes cluster resources, so the LLM can analyze them and provide cluster improvement or issue resolution based on user request")


class InitialQuestions(BaseModel):
    improvements: list[str] = Field(description="The set of questions one can ask LLM to analyze the state of their kubernetes cluster or resolve an issue on their kubernetes cluster")
