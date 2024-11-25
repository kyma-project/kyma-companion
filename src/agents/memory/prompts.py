MESSAGES_SUMMARY_PROMPT = """
Your task is to summarize the main points discussed in the given chat history. 
Your output will be used as context for other LLM agents to respond to user queries. 
Therefore, summarize in such a way that is most useful for other agents to understand the chat.

Your tasks are as follows:
Step 1: Analyze provided chat history and identify different topics, problems, proposed solutions or questions discussed.
Step 2: Generate a summary for each identified topic, problem, proposed solutions or questions as a separate paragraph.
Step 3: If the first message is a summary of older messages, then incorporate it in the most relevant summary.
Step 3: Append the summaries to final output.

Instructions:
- Do not exclude any important information.
- You can use bullet points to list different points discussed.
- Do not hallucinate or add any information that is not present in the chat history.
- Prioritize the latest messages.
"""
