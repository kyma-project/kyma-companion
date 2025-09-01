TOOL_CALLING_ERROR_HANDLING = """
## Failure Response Strategy

When a tool call fails, follow this protocol:

- ANALYZE THE FAILURE : Determine the type and likely cause of failure
- EVALUATE ALTERNATIVES : Consider if a different tool or approach might work , Check for missing or malformed parameters.
- INFORM THE USER : Acknowledge the user about the failure.

## Retry Logic for error handling:
- If a tool call fails analyze the error and attempt to fix the issue:
  -- Check for missing or malformed parameters.
  -- Verify if the correct tool is assigned with correct name.
- If three consecutive tool calls request fail, do not attempt further tool calls. Instead, respond to the user with:
  -- A clear acknowledgment of the issue (e.g., "I encountered an error while retrieving the information.").
  -- A concise explanation (if helpful) without technical details.
"""


CHUNK_SUMMARIZER_PROMPT = """
            "Focusing on the query: '{query}'\n\n"
            "Summarize this text, extracting key points relevant to the query:\n"
            "{tool_response_chunk}\n\n"
            "Summary (keep it concise, no preamble):"
        """

JOULE_CONTEXT_INFORMATION = """
Joule enhances your workflow by using the active resource in your Kyma dashboard as the context for your queries. 
This ensures that when you ask questions, Joule delivers relevant and tailored answers specific to the resource you're engaged with, making your interactions both efficient and intuitive.
"""
