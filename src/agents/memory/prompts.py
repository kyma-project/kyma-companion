MESSAGES_SUMMARY_PROMPT = """
Your task is to summarize the given conversation. 
Your output will be used as context for other LLM agents to respond to user queries. 
Therefore, summarize in such a way the is most useful for other agents to understand the conversation.

Instructions:
- Give more priority to the latest messages in the conversation.
- Focus on the technical issues discussed and the solutions proposed.
- If multiple topics are discussed, summarize each topic separately.
- Keep the summary clear and concise.
"""
