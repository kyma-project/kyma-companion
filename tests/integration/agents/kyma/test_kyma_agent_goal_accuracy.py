import pytest
from langchain_core.messages import HumanMessage, SystemMessage
from ragas.dataset_schema import MultiTurnSample
from ragas.integrations.langgraph import convert_to_ragas_messages
from ragas.llms import LangchainLLMWrapper
from ragas.messages import ToolCall
from ragas.metrics import AgentGoalAccuracyWithReference
from ragas.metrics._string import NonLLMStringSimilarity
from ragas.metrics._tool_call_accuracy import ToolCallAccuracy

from agents.common.state import SubTask
from agents.kyma.agent import KymaAgent
from agents.kyma.state import KymaAgentState
from services.data_sanitizer import DataSanitizer
from services.k8s import IK8sClient, K8sAuthHeaders, K8sClient
from utils.settings import (
    MAIN_MODEL_NAME,
    TEST_CLUSTER_AUTH_TOKEN,
    TEST_CLUSTER_CA_DATA,
    TEST_CLUSTER_CLIENT_CERTIFICATE_DATA,
    TEST_CLUSTER_CLIENT_KEY_DATA,
    TEST_CLUSTER_URL,
)

AGENT_STEPS_NUMBER = 25
TOOL_ACCURACY_THRESHOLD = 0.7


# Test data definitions
class TestCase:
    def __init__(
        self,
        name: str,
        state: KymaAgentState,
        expected_tool_calls: list[ToolCall] = None,
        expected_response: str = None,
        expected_goal: str = None,
        should_raise: bool = False,
    ):
        self.name = name
        self.state = state
        self.expected_tool_calls = expected_tool_calls
        self.expected_response = expected_response
        self.expected_goal = expected_goal
        self.should_raise = should_raise


def create_k8s_client():
    data_sanitizer = DataSanitizer()
    k8s_auth_headers = K8sAuthHeaders(
        x_cluster_url=TEST_CLUSTER_URL,
        x_cluster_certificate_authority_data=TEST_CLUSTER_CA_DATA,
        x_k8s_authorization=TEST_CLUSTER_AUTH_TOKEN,
        x_client_certificate_data=TEST_CLUSTER_CLIENT_CERTIFICATE_DATA,
        x_client_key_data=TEST_CLUSTER_CLIENT_KEY_DATA,
    )
    # Initialize k8s client for the request.
    k8s_client: IK8sClient = K8sClient.new(
        k8s_auth_headers=k8s_auth_headers,
        data_sanitizer=data_sanitizer,
    )
    return k8s_client


@pytest.fixture
def k8s_client():
    # Initialize k8s client for the request.
    k8s_client: IK8sClient = create_k8s_client()
    return k8s_client


@pytest.fixture
def kyma_agent(app_models):
    return KymaAgent(app_models)


# Helper functions for test simplification
def create_system_message(resource_info: dict) -> SystemMessage:
    """Create a system message with resource information."""
    return SystemMessage(content=f"The user query is related to: {resource_info}")


def create_basic_state(
    task_description: str,
    messages: list = None,
    k8s_client: IK8sClient = None,
) -> KymaAgentState:
    """Create a basic KymaAgentState with common fields."""
    return KymaAgentState(
        agent_messages=[],
        messages=messages,
        subtasks=[
            {
                "description": task_description,
                "task_title": task_description,
                "assigned_to": "KymaAgent",
            }
        ],
        my_task=SubTask(
            description=task_description,
            task_title=task_description,
            assigned_to="KymaAgent",
        ),
        k8s_client=k8s_client,
        is_last_step=False,
        remaining_steps=AGENT_STEPS_NUMBER,
    )


@pytest.fixture
def tool_accuracy_scorer():
    metric = ToolCallAccuracy()
    metric.arg_comparison_metric = NonLLMStringSimilarity()
    return metric


@pytest.fixture
def evaluator_llm(app_models):
    main_model = app_models[MAIN_MODEL_NAME]
    return LangchainLLMWrapper(main_model.llm)


@pytest.fixture
def goal_accuracy_metric(evaluator_llm):
    scorer = AgentGoalAccuracyWithReference(llm=evaluator_llm)
    return scorer


async def call_kyma_agent(kyma_agent, state):
    response = await kyma_agent.agent_node().ainvoke(state)
    return response


def create_test_cases(k8s_client: IK8sClient):
    """Fixture providing test cases for Kyma agent testing."""
    return [
        TestCase(
            "Should find accessStrategies field in the API Rule and then use Kyma Doc Search Tool Calls to find the correct configuration",
            state=create_basic_state(
                task_description="What is wrong with api rule?",
                messages=[
                    SystemMessage(
                        content="The user query is related to: {'resource_api_version': 'gateway.kyma-project.io/v1beta1', "
                        "'resource_namespace': 'test-apirule-7', 'resource_kind': 'APIRule', 'resource_name': 'restapi'}"
                    ),
                    HumanMessage(content="What is wrong with api rule?"),
                ],
                k8s_client=k8s_client,
            ),
            expected_goal="The API Rule is not valid. The error is that the accessStrategies field has multiple entries, which is not allowed. The correct configuration should have only one accessStrategy entry.",
        ),
        TestCase(
            "Should find javascript Dates syntax error in Kyma function",
            state=create_basic_state(
                task_description="What is wrong with function?",
                messages=[
                    SystemMessage(
                        content="The user query is related to: {'resource_api_version': 'serverless.kyma-project.io/v1alpha2', "
                        "'resource_namespace': 'test-function-8', 'resource_kind': 'Function', 'resource_name': 'restapi'}"
                    ),
                    HumanMessage(content="What is wrong with function?"),
                ],
                k8s_client=k8s_client,
            ),
            expected_goal="There is a syntax error in the JavaScript code. Date must be used instead of Dates.",
        ),
    ]


@pytest.mark.parametrize("test_case", create_test_cases(create_k8s_client()))
@pytest.mark.asyncio
async def test_kyma_agent(kyma_agent, goal_accuracy_metric, test_case: TestCase):
    """
    Simplified test for KymaAgent _invoke_chain method.
    Tests both tool calling and content response scenarios.
    """
    agent_response = await call_kyma_agent(kyma_agent, test_case.state)
    agent_messages = convert_to_ragas_messages(agent_response["agent_messages"])

    sample = MultiTurnSample(
        user_input=agent_messages,
        reference=test_case.expected_goal,
    )

    score = await goal_accuracy_metric.multi_turn_ascore(sample)
    assert (
        score > TOOL_ACCURACY_THRESHOLD
    ), f"Tool call accuracy ({score:.2f}) is below the acceptable threshold of {TOOL_ACCURACY_THRESHOLD}"
