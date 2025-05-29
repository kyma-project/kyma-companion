import uuid
from unittest.mock import patch

import pytest
from deepeval import assert_test
from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCase, LLMTestCaseParams
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import StateSnapshot

from followup_questions.followup_questions import FollowUpQuestionsHandler
from services.conversation import ConversationService
from utils.settings import MAIN_MODEL_MINI

FOLLOW_UP_QUESTIONS_COUNT = 5

shared_memory = {}


@pytest.fixture
def followup_correctness_metric(evaluator_model):
    return GEval(
        name="Correctness",
        evaluation_steps=[
            "Check whether each line is a valid question",
            "Check if each questions is related to either Kubernetes or SAP Kyma runtime",
            "Check if each question is not a question to user",
        ],
        evaluation_params=[
            LLMTestCaseParams.ACTUAL_OUTPUT,
        ],
        model=evaluator_model,
        threshold=0.5,
        async_mode=False,
    )


@pytest.fixture(scope="session")
def conversation_service(app_models, companion_graph):
    with patch("services.conversation.ConversationService.__init__") as mock_cs:
        model_mini = app_models[MAIN_MODEL_MINI]
        mock_cs.return_value = None
        conversation_service = ConversationService()
        conversation_service._companion_graph = companion_graph
        conversation_service._model_mini = model_mini
        conversation_service._followup_questions_handler = FollowUpQuestionsHandler(
            model=model_mini
        )

    async def mock_aget_state(config):
        con_id = config["configurable"]["thread_id"]
        return shared_memory[con_id]

    conversation_service._companion_graph.graph.aget_state = mock_aget_state
    return conversation_service


@pytest.mark.parametrize(
    "messages",
    [
        [
            SystemMessage(
                content="""
                        The user query is related to: {'resource_api_version': 'v1', 'resource_namespace': 'nginx-oom'}
                        """
            ),
            HumanMessage(content="What is Kyma?"),
            AIMessage(
                name="KymaAgent",
                content="""
                        Kyma is an open-source platform designed to extend
                        applications with microservices and serverless functions. It provides a set of tools and
                        components that enable developers to build, deploy, and manage cloud-native applications. Key
                        features of Kyma include: 1. **Kubernetes-based**: Kyma runs on Kubernetes, leveraging its
                        orchestration capabilities for managing containerized applications. 2. **Microservices
                        Architecture**: It supports the development of microservices, allowing for modular application
                        design and easier scaling. 3. **Serverless Functions**: Kyma enables the creation of serverless
                        functions, which can be triggered by events, making it easier to build 
                        event-driven applications.
                        4. **Integration Capabilities**: It offers various integration options with external services 
                        and
                        APIs, facilitating seamless communication between different systems. 5. **Extensibility**:
                        Developers can extend existing applications with new functionalities without needing to modify
                        the core application code. 6. **Service Management**: Kyma provides tools for managing services,
                        including service discovery, monitoring, and logging. Overall, Kyma is aimed at simplifying the
                        development and management of cloud-native applications, making it easier for organizations to
                        innovate and respond to changing business needs.
                        """,
            ),
        ],
        [
            SystemMessage(
                content="The user query is related to: "
                "{'resource_api_version': 'v1', 'resource_namespace': 'nginx-oom'}"
            ),
            HumanMessage(content="why is the pod failing?"),
            AIMessage(
                content="The `nginx` container in the `nginx-5dbddc77dd-t5fm2` pod is experiencing a "
                "`CrashLoopBackOff` state. The last termination reason was `StartError`"
                " with the message indicating a failure to create the containerd task "
                "due to a context cancellation."
            ),
        ],
    ],
)
@pytest.mark.asyncio
async def test_followup_questions(
    messages, conversation_service, followup_correctness_metric
):
    # Given: a conversation state with messages
    given_latest_state = StateSnapshot(
        values={
            "messages": messages,
        },
        next=(),
        config=RunnableConfig(),
        tasks=(),
        metadata=None,
        created_at=None,
        parent_config=None,
    )

    given_conversation_id = str(uuid.uuid4())
    shared_memory[given_conversation_id] = given_latest_state

    # When: the followup questions handler is invoked
    result = await conversation_service.handle_followup_questions(given_conversation_id)

    # Then: there should be 5 follow-up questions.
    assert len(result) == FOLLOW_UP_QUESTIONS_COUNT

    got_questions = "\n".join(result)
    test_case = LLMTestCase(
        input=messages[-1].content,
        actual_output=got_questions,
    )
    assert_test(test_case, [followup_correctness_metric], run_async=False)
