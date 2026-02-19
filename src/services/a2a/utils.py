import json


def extract_response_from_chunk(chunk: str) -> str | None:
        """Extract the response content from a graph chunk."""
        try:
            chunk_data = json.loads(chunk)
            for node_name, node_output in chunk_data.items():
                if isinstance(node_output, dict) and "messages" in node_output:
                    messages = node_output["messages"]
                    for msg in messages:
                        if isinstance(msg, dict) and "content" in msg:
                            return str(msg["content"])
                        elif hasattr(msg, "content"):
                            return str(getattr(msg, "content"))
        except (json.JSONDecodeError, KeyError, TypeError):
            pass
        return None