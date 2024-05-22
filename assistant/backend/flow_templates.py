from langchain import hub

FOLLOW_UP_QUESTIONS = """
<instructions>
You are an expert in Kubernetes. Analyze the following chat context from a user question and the answer of a smart assistant.
Consider the key points and essential details that are necessary for understanding the situation.
Focus on technical details and consider the previously answered question.

Then, come up with a minimum of 1 and a maximum of 4 follow-up questions. Provide fewer but more relevant questions.
In your answer, follow the format instructions below.  
</instructions>

<conversation-context>
{context}
</conversation-context>

<format-instructions>
{format_instructions}
</format-instructions>

"""

GENERATE_INITIAL_QUESTIONS = """
<instructions>
You are an AI-powered Kubernetes and Kyma assistant designed to efficiently troubleshoot cluster issues and provide insightful analysis for users.
Complete the provided task. When completing the task, consider the following format <format-instructions> and <question-criteria>. 
</instructions>

<format-instructions>
{format_instructions}
</format-instructions>

<question-criteria>
- Prioritize questions that identify potential issues using phrases like "wrong with," "causing," or "be improved."
- Questions are sorted from general to more specific.
- Prioritize quality over quantity; fewer questions but each highly relevant.
- Ensure variety in the questions; do not repeat similar queries.
- Questions are concise yet clear, with a minimum of 2 words and a maximum of 10 words.
</question-criteria>

<task>
  **Step 1: General Questions**
  - Generate 1-2 general questions about the cluster health or application behavior, following the format of these questions:
    - "Why is my <resource> not working?"
    - "How can I fix my <resource>?"
    - "What is wrong with my <resource>?"

  **Step 2: Specific Questions based on Cluster Information**
  - Analyze the provided cluster-information:
    {context}
  - Generate 2-3 specific questions that investigate potential issues identified in the general questions.
  
  Include at least one general question.
</task>
"""

