MESSAGES_SUMMARY_PROMPT = """
Summarize the following conversation to be used as context to LLM calls. 
Give more priority to the latest messages.
Focus on the main issues and solutions proposed. 
If multiple topics are discussed in the conversation, then summarize each topic separately.
Keep the summary clear and concise.
"""