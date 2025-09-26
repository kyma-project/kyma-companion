import pytest
from langchain_core.messages import HumanMessage, SystemMessage
from ragas.dataset_schema import SingleTurnSample
from ragas.integrations.langgraph import convert_to_ragas_messages
from ragas.llms import LangchainLLMWrapper
from ragas.messages import ToolCall
from ragas.metrics import SimpleCriteriaScore

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
GOAL_ACCURACY_THRESHOLD = 7


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
    return SystemMessage(content=f"{resource_info}")


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
def evaluator_llm(app_models):
    main_model = app_models[MAIN_MODEL_NAME]
    return LangchainLLMWrapper(main_model.llm)


@pytest.fixture
def goal_accuracy_metric(evaluator_llm):
    scorer = SimpleCriteriaScore(
        name="course_grained_score",
        definition="Score 0 to 10 by similarity",
        llm=evaluator_llm,
    )
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
                        content="{'resource_api_version': 'gateway.kyma-project.io/v1beta1', "
                        "'resource_namespace': 'test-apirule-7', 'resource_kind': 'APIRule', 'resource_name': 'restapi'}"
                    ),
                    HumanMessage(content="What is wrong with api rule?"),
                ],
                k8s_client=k8s_client,
            ),
            expected_goal="The API Rule has validation errors. The error is that accessStrategies field has multiple entries, "
            "which is not allowed. The correct configuration should have only one accessStrategy entry.",
        ),
        TestCase(
            "Should find javascript Dates syntax error in Kyma function",
            state=create_basic_state(
                task_description="What is wrong with function?",
                messages=[
                    SystemMessage(
                        content="{'resource_api_version': 'serverless.kyma-project.io/v1alpha2', "
                        "'resource_namespace': 'test-function-8', 'resource_kind': 'Function', 'resource_name': 'func1'}"
                    ),
                    HumanMessage(content="What is wrong with function?"),
                ],
                k8s_client=k8s_client,
            ),
            expected_goal="There is a syntax error in the JavaScript code. Date must be used instead of Dates.",
        ),
        TestCase(
            "Should ask more information from user for queries about Kyma resources status",
            state=create_basic_state(
                task_description="what is the status of all Kyma resources?",
                messages=[
                    HumanMessage(content="what is the status of all Kyma resources?"),
                ],
                k8s_client=k8s_client,
            ),
            expected_goal="Agent response should explain that user query is very broad and ask user to provide specific details",
        ),
        TestCase(
            "Should ask more information from user for queries about all Kyma resources in cluster",
            state=create_basic_state(
                task_description="check all Kyma resources",
                messages=[
                    HumanMessage(content="check all Kyma resources"),
                ],
                k8s_client=k8s_client,
            ),
            expected_goal="Agent response should explain that user query is very broad and ask user to provide specific details",
        ),
        TestCase(
            "Should ask more information from user for queries about Kyma resources health",
            state=create_basic_state(
                task_description="are all Kyma resources healthy?",
                messages=[
                    HumanMessage(content="are all Kyma resources healthy?"),
                ],
                k8s_client=k8s_client,
            ),
            expected_goal="Agent response should explain that user query is very broad and ask user to provide specific details",
        ),
        TestCase(
            "Should ask more information from user for queries about all Kyma resources in cluster",
            state=create_basic_state(
                task_description="is there anything wrong with Kyma resources?",
                messages=[
                    HumanMessage(
                        content="is there anything wrong with Kyma resources?"
                    ),
                ],
                k8s_client=k8s_client,
            ),
            expected_goal="Agent response should explain that user query is very broad and ask user to provide specific details",
        ),
        TestCase(
            "Should ask more information from user for queries about showing all Kyma resources",
            state=create_basic_state(
                task_description="show me all Kyma resources",
                messages=[
                    HumanMessage(content="show me all Kyma resources"),
                ],
                k8s_client=k8s_client,
            ),
            expected_goal="Agent response should explain that user query is very broad and ask user to provide specific details",
        ),
        TestCase(
            "Should ask more information from user for queries about all Kyma resources in cluster",
            state=create_basic_state(
                task_description="what is wrong with Kyma?",
                messages=[
                    HumanMessage(content="what is wrong with Kyma?"),
                ],
                k8s_client=k8s_client,
            ),
            expected_goal="Agent response should explain that user query is very broad and ask user to provide specific details",
        ),
        TestCase(
            "Should ask more information from user for queries about Kyma cluster state",
            state=create_basic_state(
                task_description="show me the state of Kyma cluster",
                messages=[
                    HumanMessage(content="show me the state of Kyma cluster"),
                ],
                k8s_client=k8s_client,
            ),
            expected_goal="Agent response should explain that user query is very broad and ask user to provide specific details",
        ),
    ]


@pytest.mark.parametrize("test_case", create_test_cases(create_k8s_client()))
@pytest.mark.asyncio
async def test_kyma_agent(kyma_agent, goal_accuracy_metric, test_case: TestCase):
    """
    Simplified test for KymaAgent _invoke_chain method.
    Tests content response scenarios.
    """
    user_query = test_case.state.messages[-1].content
    agent_response = await call_kyma_agent(kyma_agent, test_case.state)
    agent_messages = convert_to_ragas_messages(agent_response["agent_messages"])

    sample = SingleTurnSample(
        user_input=user_query,
        response=agent_messages[-1].content,
        reference=test_case.expected_goal,
    )

    score = await goal_accuracy_metric.single_turn_ascore(sample)
    if score < GOAL_ACCURACY_THRESHOLD:
        print(
            f"**Test case failed to meet expectation:**\n"
            f"--> Expected goal: {test_case.expected_goal}\n"
            f"--> Agent response: \n{agent_messages[-1].content}"
        )

    assert score >= GOAL_ACCURACY_THRESHOLD, (
        f"Test case: {test_case.name}. "
        f"Tool call accuracy ({score:.2f}) is below the acceptable threshold of {GOAL_ACCURACY_THRESHOLD}"
    )
