PLANNER = "Planner"

SUMMARIZATION = "Summarization"
INITIAL_SUMMARIZATION = "InitialSummarization"

CLUSTER = "cluster"

UNKNOWN = "unknown"

NAMESPACED = "namespaced"

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

FEEDBACK = "feedback"

IS_FEEDBACK = "is_feedback"

RESPONSE_QUERY_OUTSIDE_DOMAIN = (
    "This question appears to be outside my domain of expertise. "
    "If you have any technical or Kyma related questions, I'd be happy to help."
)

RESPONSE_HELLO = "Hello! How can I assist you with Kyma or Kubernetes today?"

RESPONSE_UNABLE_TO_PROCESS = (
    "I'm currently unable to process your request. "
    "Please try again later or ask a different question."
)

ERROR_RESPONSE = (
    "We encountered an error while processing your request. "
    "Please try again shortly. Thank you for your patience!"
)
