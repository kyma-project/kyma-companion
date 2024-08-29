from os import getenv
from types import Protocol

from dotenv import load_dotenv
from gen_ai_hub.proxy.langchain.openai import ChatOpenAI
from langchain_core.messages.base import BaseMessage
from langchain_core.prompts import PromptTemplate

CONVERSATION_TEMPLATE = """
You are an AI-powered Kubernetes and Kyma assistant designed to efficiently troubleshoot cluster issues and provide insightful analysis for users.
Complete the provided task. Your general task is to generate questions based on the given cluster information.

Your tasks are as follows:
**Step 1: Specific Questions based on Cluster Information**
- Analyze the provided <cluster-information>
- Generate 2-3 specific questions that investigate potential issues identified in the general questions.

**Step 2: Improvement Questions**
- Generate 2-3 questions about how the cluster or the resource can be improved, following the format of these questions:
- "How can I improve my <resource>?"
- "How can I follow best practices for my <resource>?"

**Step 3: General Questions**
- Generate 1-2 general questions about the cluster, resource or application behavior, following the format of these questions:
- "What is the role of <resource>?"
- "What is the concept of <resource>?"

**Step 4: Select Questions according to the Cluster Information**
- Identify errors in the <cluster-information>.
- If errors are found:
  - Return questions from Step 1 and Step 3.
- If no errors are found:
  - Return questions from Step 2 and Step 3.

In general:
- Prioritize questions that identify potential issues using phrases like "wrong with," "causing," or "be improved."
- Questions are sorted from general to more specific.
- Prioritize quality over quantity; fewer questions but each highly relevant.
- Ensure variety in the questions; do not repeat similar queries.
- Questions are concise yet clear, with a minimum of 2 words and a maximum of 10 words.

The only thing you return are the questions, without any numbering, each seperated by a newline.

The provided cluster information is:

{context}
""" 

class ChatOpenAIInterface(Protocol):
    def invoke(self, prompt: str) -> BaseMessage:
        ...

class InitialQuestionsInterface(Protocol):
    def generate_questions(self, template: str, context: str) -> list[str]:
        ...

class InitialQuestions:
    ChatOpenAI: ChatOpenAIInterface

    def __init__(self, llm: ChatOpenAIInterface) -> None:
        pass
    
    @staticmethod
    def get_gpt4o_instance(temperature: float = 0.5) -> ChatOpenAIInterface:
        load_dotenv()
        model = ChatOpenAI(
            model_name="gpt-4.o",
            temperature=temperature,
            deployment_id=getenv("AICORE_DEPLOYMENT_ID_GPT4"),
            config_id=getenv("AICORE_CONFIGURATION_ID_GPT4"),
        )
        return model

    def generate_questions(self, template: str, context: str) -> list[str]:
        # Format promp and send to llm.
        prompt = PromptTemplate(
            template=template,
            input_variables=['context'],
        )
        prompt = prompt.format(context=context)
        result = self.llm.invoke(prompt)
        
        # Extract questions from result.
        lines: list[str] = []
        for line in result.content.__str__().split("\n"):
            if line.strip() == "":
                continue
            lines.append(line)

        return lines
