from collections import defaultdict

PLANNER = "Planner"

SUMMARIZATION = "Summarization"
INITIAL_SUMMARIZATION = "InitialSummarization"

FINALIZER = "Finalizer"

GATEKEEPER = "Gatekeeper"

EXIT = "Exit"

CONTINUE = "Continue"

RECENT_MESSAGES_LIMIT = 10

MESSAGES = "messages"

MESSAGES_SUMMARY = "messages_summary"

AGENT_MESSAGES = "agent_messages"

AGENT_MESSAGES_SUMMARY = "agent_messages_summary"

ERROR = "error"

NEXT = "next"

SUBTASKS = "subtasks"

FINAL_RESPONSE = "final_response"

GRAPH_STEP_TIMEOUT_SECONDS = 60

IS_LAST_STEP = "is_last_step"

K8S_CLIENT = "k8s_client"

MY_TASK = "my_task"

QUERY = "query"

OWNER = "owner"

K8S_AGENT = "KubernetesAgent"

K8S_AGENT_TASK_DESCRIPTION = "Fetching data from Kubernetes"

KYMA_AGENT = "KymaAgent"

KYMA_AGENT_TASK_DESCRIPTION = "Fetching data from Kyma"

COMMON = "Common"

COMMON_TASK_DESCRIPTION = "Answering general queries"

RESPONSE_CONVERTER = "ResponseConverter"

NEW_YAML = "New"

UPDATE_YAML = "Update"

SUCCESS_CODE = 200

ERROR_RATE_LIMIT_CODE = 429

K8S_API_PAGINATION_LIMIT = 50

K8S_API_PAGINATION_MAX_PAGE = 2

TOOL_RESPONSE_TOKEN_COUNT_LIMIT = defaultdict(
    lambda: 16000,  # Default token limit if model not found
    {
        "gpt-4o": 100000,  # GPT-4o supports 128K context
        "gpt-4o-mini": 100000,  # GPT-4o Mini supports 128K context
        "gpt-3.5": 12000,  # GPT-3.5 Turbo supports ~16K tokens
        "gemini-1.0-pro": 28000,  # Gemini 1.0 Pro supports 32K tokens
    },
)

TOTAL_CHUNKS_LIMIT = 3  # Limit the number of allowed chunking of tool response
