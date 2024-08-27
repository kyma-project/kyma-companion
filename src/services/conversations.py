### TODO: the following code is just a temporary placeholder.
### It will be replaced with the implementation 
### of langgraph.

from os import getenv

from dotenv import load_dotenv
from gen_ai_hub.proxy.langchain.openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate

### TODO: In line 2 of 'instructions' an 'example' is mentioned (in the original of this template).
### Was this actually used? If not, let's remove it. If it was, how was it added?
CONVERSATION_TEMPLATE = """
You are an AI-powered Kubernetes and Kyma assistant designed to efficiently troubleshoot cluster issues and provide insightful analysis for users.
Complete the provided task. When completing the task, consider the <question-criteria> and the <example>. 

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

def get_gpt4o_instance(temperature: float = 0.5) -> ChatOpenAI:
    load_dotenv()
    model = ChatOpenAI(
        model_name="gpt-4.o",
        temperature=temperature,
        deployment_id=getenv("AICORE_DEPLOYMENT_ID_GPT4"),
        config_id=getenv("AICORE_CONFIGURATION_ID_GPT4"),
    )
    return model

def _generate_questions(context: str, llm: ChatOpenAI) -> list[str]:
    prompt = PromptTemplate(
        template=CONVERSATION_TEMPLATE,
        input_variables=['context']
    )
    prompt = prompt.format(context=context)
    result = llm.invoke(prompt)
    questions = _extract_questions_from_output(result.content)

    return questions

def _extract_questions_from_output(output: str) -> list[str]:
    lines: list[str] = []
    for line in output.split("\n"):
        if line.strip() == "":
            continue
        lines.append(line)
    return lines

def get_questions(context: str) -> str:
    llm = get_gpt4o_instance()
    questions = _generate_questions(context, llm)
    return questions

if __name__ == "__main__":
    context = "the pod 'mypod' in the namespace 'mynamespace' is not running; the status is 'CrashLoopBackOff', and the container 'mycontainer' is failing to start."
    questions = get_questions(context=context)
    print(questions)
