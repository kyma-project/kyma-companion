MESSAGES_SUMMARIZATION_INSTRUCTIONS = """
- Do not hallucinate or add any extra information, troubleshooting steps and recommendations not present in the original conversation.
- Ensure all important information is included.
- Use bullet points to list different points discussed.
- Each bullet point should start with a hyphen (-).
- Prioritize the latest messages.
- Remove duplicate summaries and only keep the latest 10 summaries.
- Be concise and relevant to the original content.
"""

MESSAGES_SUMMARIZATION_PROMPT = f"""
Your task is to summarize the main issues, points or topics discussed in the given chat history.
Your output will be used as context for other LLM agents to respond to user queries.
Therefore, summarize in such a way that is most useful for other agents to understand the chat.

Your tasks are as follows:
Step 1: Analyze provided chat history and identify different topics, problems, issues, proposed solutions or questions discussed.
Step 2: Generate a summary for each identified topic, problem, issue, proposed solutions or questions as a separate paragraph.
Step 3: If the first message is a summary of older messages, then incorporate it in the most relevant summary.
Step 3: Append the summaries to final output.

Important Instructions:
{MESSAGES_SUMMARIZATION_INSTRUCTIONS}
"""
