from unittest.mock import Mock

import pytest
from deepeval import assert_test
from deepeval.metrics import (
    FaithfulnessMetric,
    GEval,
)
from deepeval.test_case import LLMTestCase, LLMTestCaseParams
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from agents.common.state import SubTask
from agents.kyma.agent import KymaAgent
from agents.kyma.state import KymaAgentState
from integration.agents.fixtures.api_rule import (
    API_RULE_WITH_CONFLICT_ACCESS_STRATEGIES,
    EXPECTED_API_RULE_RESPONSE,
    KYMADOC_FOR_API_RULE_VALIDATION_ERROR,
)
from integration.agents.fixtures.btp_manager import (
    EXPECTED_BTP_MANAGER_RESPONSE,
    RETRIEVAL_CONTEXT,
)
from integration.agents.fixtures.serverless_function import (
    EXPECTED_SERVERLESS_FUNCTION_RESPONSE,
    EXPECTED_SERVERLESS_FUNCTION_RESPONSE_NO_REPLICAS,
    FUNCTION_NO_REPLICAS,
    KYMADOC_FOR_SERVERLESS_FUNCTION_POD_NOT_READY,
    KYMADOC_FUNCTION_TROUBLESHOOTING,
    SERVERLESS_FUNCTION_WITH_SYNTAX_ERROR,
)
from services.k8s import IK8sClient
from utils.settings import DEEPEVAL_TESTCASE_VERBOSE

AGENT_STEPS_NUMBER = 25


@pytest.fixture
def kyma_agent(app_models):
    return KymaAgent(app_models)


@pytest.fixture
def correctness_metric(evaluator_model):
    return GEval(
        name="Correctness",
        evaluation_params=[
            LLMTestCaseParams.ACTUAL_OUTPUT,
            LLMTestCaseParams.EXPECTED_OUTPUT,
        ],
        evaluation_steps=[
            "Evaluate whether two answers are semantically similar or convey the same meaning."
            "Check whether the facts in 'actual output' contradict any facts in 'expected output'",
            "Lightly penalize omissions of detail, focusing on the main idea",
            "Vague language are permissible",
        ],
        model=evaluator_model,
        threshold=0.7,
    )


@pytest.fixture
def faithfulness_metric(evaluator_model):
    return FaithfulnessMetric(
        threshold=0.7,
        model=evaluator_model,
        include_reason=True,
        verbose_mode=DEEPEVAL_TESTCASE_VERBOSE,
    )


def assert_tool_call(response: AIMessage, expected_tool: str) -> None:
    """Assert the immediate next tool decision matches the expected tool."""
    tool_calls = response.tool_calls or []
    actual = tool_calls[0].get("name") if tool_calls else None
    assert actual == expected_tool, f"Expected next tool '{expected_tool}', got '{actual}'."


@pytest.mark.parametrize(
    "test_case,state,retrieval_context,expected_result,should_raise",
    [
        (
            "Should mention about resource context in kyma dashboard",
            KymaAgentState(
                agent_messages=[],
                messages=[
                    SystemMessage(
                        content="{'resource_kind': 'Function', 'resource_api_version': 'serverless.kyma-project.io/v1alpha2'}"
                    ),
                    HumanMessage(content="Why is the pod of the serverless Function not ready?"),
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "id": "tool_call_id_1",
                                "type": "tool_call",
                                "name": "kyma_query_tool",
                                "args": {"uri": "/apis/serverless.kyma-project.io/v1alpha2/functions"},
                            },
                        ],
                    ),
                    ToolMessage(
                        content="Please specify the function name.",
                        name="kyma_query_tool",
                        tool_call_id="tool_call_id_1",
                    ),
                ],
                subtasks=[
                    {
                        "description": "Why is the pod of the serverless Function not ready?",
                        "task_title": "Why is the pod of the serverless Function not ready?",
                        "assigned_to": "KymaAgent",
                    }
                ],
                my_task=SubTask(
                    description="Why is the pod of the serverless Function not ready?",
                    task_title="Why is the pod of the serverless Function not ready?",
                    assigned_to="KymaAgent",
                ),
                k8s_client=Mock(spec_set=IK8sClient),  # noqa
                is_last_step=False,
                remaining_steps=AGENT_STEPS_NUMBER,
            ),
            None,
            "I need more information to answer this question. Please provide the name and namespace of the Function whose pod is not ready. This will help me investigate the specific issue and provide a solution tailored to your resource. ",
            False,
        ),
        # Test case for API Rule with conflict access strategies
        # - Verifies agent correctly identifies and explains API Rule validation error
        # - Checks agent uses both kyma_query_tool and search_kyma_doc
        # - Validates response matches expected explanation about conflict access strategies
        (
            "Should return right solution for API Rule with wrong access strategy",
            KymaAgentState(
                agent_messages=[],
                messages=[
                    SystemMessage(
                        content="{'resource_kind': 'APIRule', 'resource_api_version': 'gateway.kyma-project.io/v2', 'resource_name': 'restapi', 'resource_namespace': 'kyma-app-apirule-broken'}"
                    ),
                    HumanMessage(content="What is wrong with the APIRule?"),
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "id": "tool_call_id_1",
                                "type": "tool_call",
                                "name": "kyma_query_tool",
                                "args": {
                                    "uri": "/apis/gateway.kyma-project.io/v2/namespaces/kyma-app-apirule-broken/apirules"
                                },
                            }
                        ],
                    ),
                    ToolMessage(
                        content=API_RULE_WITH_CONFLICT_ACCESS_STRATEGIES,
                        name="kyma_query_tool",
                        tool_call_id="tool_call_id_1",
                    ),
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "id": "tool_call_id_2",
                                "type": "tool_call",
                                "name": "search_kyma_doc",
                                "args": {"query": "APIRule validation errors"},
                            }
                        ],
                    ),
                    ToolMessage(
                        content=KYMADOC_FOR_API_RULE_VALIDATION_ERROR,
                        name="search_kyma_doc",
                        tool_call_id="tool_call_id_2",
                    ),
                ],
                subtasks=[
                    {
                        "description": "What is wrong with the APIRule?",
                        "task_title": "What is wrong with the APIRule?",
                        "assigned_to": "KymaAgent",
                    }
                ],
                my_task=SubTask(
                    description="What is wrong with the APIRule?",
                    task_title="What is wrong with the APIRule?",
                    assigned_to="KymaAgent",
                ),
                k8s_client=Mock(spec_set=IK8sClient),
                is_last_step=False,
                remaining_steps=AGENT_STEPS_NUMBER,
            ),
            KYMADOC_FOR_API_RULE_VALIDATION_ERROR,
            EXPECTED_API_RULE_RESPONSE,
            False,
        ),
        # Test case for Serverless Function with syntax error
        # - Verifies agent correctly identifies JavaScript syntax error
        # - Validates response includes proper error explanation
        (
            "Should return right solution for Serverless Function with syntax error",
            KymaAgentState(
                agent_messages=[],
                messages=[
                    SystemMessage(
                        content="{'resource_kind': 'Function', 'resource_api_version': 'serverless.kyma-project.io/v1alpha2', 'resource_name': 'func1', 'resource_namespace': 'kyma-app-serverless-syntax-err'}"
                    ),
                    HumanMessage(content="what is wrong?"),
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "id": "tool_call_id_1",
                                "type": "tool_call",
                                "name": "kyma_query_tool",
                                "args": {
                                    "uri": "/apis/serverless.kyma-project.io/v1alpha2/namespaces/kyma-app-serverless-syntax-err/functions/func1"
                                },
                            }
                        ],
                    ),
                    ToolMessage(
                        content=SERVERLESS_FUNCTION_WITH_SYNTAX_ERROR,
                        name="kyma_query_tool",
                        tool_call_id="tool_call_id_1",
                    ),
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "id": "tool_call_id_2",
                                "type": "tool_call",
                                "name": "search_kyma_doc",
                                "args": {"query": "Kyma Function troubleshooting"},
                            }
                        ],
                    ),
                    ToolMessage(
                        content=KYMADOC_FUNCTION_TROUBLESHOOTING,
                        name="search_kyma_doc",
                        tool_call_id="tool_call_id_2",
                    ),
                ],
                subtasks=[
                    {
                        "description": "What is wrong with Function 'func1' in namespace 'kyma-app-serverless-syntax-err' with api version 'serverless.kyma-project.io/v1alpha2'?",
                        "task_title": "What is wrong with Function 'func1' in namespace 'kyma-app-serverless-syntax-err' with api version 'serverless.kyma-project.io/v1alpha2'?",
                        "assigned_to": "KymaAgent",
                    }
                ],
                my_task=SubTask(
                    description="What is wrong with Function 'func1' in namespace 'kyma-app-serverless-syntax-err' with api version 'serverless.kyma-project.io/v1alpha2'?",
                    task_title="What is wrong with Function 'func1' in namespace 'kyma-app-serverless-syntax-err' with api version 'serverless.kyma-project.io/v1alpha2'?",
                    assigned_to="KymaAgent",
                ),
                k8s_client=Mock(spec_set=IK8sClient),  # noqa
                is_last_step=False,
                remaining_steps=AGENT_STEPS_NUMBER,
            ),  # context
            None,  # retrieval_context
            EXPECTED_SERVERLESS_FUNCTION_RESPONSE,  # expected_result
            False,  # should_raise
        ),
        # Test case for Serverless Function with no replicas
        # - Verifies agent detects and explains replica configuration issue
        # - Validates response includes proper explanation about replica requirements
        (
            "Should return right solution for Serverless Function with no replicas",
            KymaAgentState(
                agent_messages=[],
                messages=[
                    SystemMessage(content="{'resource_namespace': 'kyma-serverless-function-no-replicas'}"),
                    HumanMessage(content="Why is the pod of the serverless Function not ready?"),
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "id": "tool_call_id_1",
                                "type": "tool_call",
                                "name": "kyma_query_tool",
                                "args": {
                                    "uri": "/apis/serverless.kyma-project.io/v1alpha2/namespaces/kyma-app-serverless-syntax-err/functions/func1"
                                },
                            },
                            {
                                "id": "tool_call_id_2",
                                "type": "tool_call",
                                "name": "search_kyma_doc",
                                "args": {"query": "serverless Function pod not ready"},
                            },
                        ],
                    ),
                    ToolMessage(
                        content=FUNCTION_NO_REPLICAS,
                        name="kyma_query_tool",
                        tool_call_id="tool_call_id_1",
                    ),
                    ToolMessage(
                        content=KYMADOC_FOR_SERVERLESS_FUNCTION_POD_NOT_READY,
                        name="search_kyma_doc",
                        tool_call_id="tool_call_id_2",
                    ),
                ],
                subtasks=[
                    {
                        "description": "Why is the pod of the serverless Function not ready?",
                        "task_title": "Why is the pod of the serverless Function not ready?",
                        "assigned_to": "KymaAgent",
                    }
                ],
                my_task=SubTask(
                    description="Why is the pod of the serverless Function not ready?",
                    task_title="Why is the pod of the serverless Function not ready?",
                    assigned_to="KymaAgent",
                ),
                k8s_client=Mock(spec_set=IK8sClient),  # noqa
                is_last_step=False,
                remaining_steps=AGENT_STEPS_NUMBER,
            ),
            None,
            EXPECTED_SERVERLESS_FUNCTION_RESPONSE_NO_REPLICAS,
            False,
        ),
        # Test case for general Kyma documentation query
        # - Verifies agent handles general documentation queries without resource lookup
        # - Checks proper use of doc search tool for BTP Operator features
        # - Validates response matches expected documentation content
        (
            "Should return right solution for general Kyma question - only need Kyma Doc Search",
            KymaAgentState(
                agent_messages=[],
                messages=[
                    SystemMessage(content="{}"),
                    HumanMessage(content="What are the BTP Operator features?"),
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "id": "tool_call_id_1",
                                "type": "tool_call",
                                "name": "search_kyma_doc",
                                "args": {"query": "BTP Operator features"},
                            }
                        ],
                    ),
                    ToolMessage(
                        content=RETRIEVAL_CONTEXT,
                        name="search_kyma_doc",
                        tool_call_id="tool_call_id_1",
                    ),
                ],
                subtasks=[
                    {
                        "description": "What are the BTP Operator features?",
                        "task_title": "What are the BTP Operator features?",
                        "assigned_to": "KymaAgent",
                    }
                ],
                my_task=SubTask(
                    description="What are the BTP Operator features?",
                    task_title="What are the BTP Operator features?",
                    assigned_to="KymaAgent",
                ),
                k8s_client=Mock(spec_set=IK8sClient),  # noqa
                is_last_step=False,
                remaining_steps=AGENT_STEPS_NUMBER,
            ),
            "",
            EXPECTED_BTP_MANAGER_RESPONSE,
            False,
        ),
        # Test case for Kyma doc search when no relevant documentation is found
        # - it still responds with the existing knowledge as BTP Operator features are known to LLM
        (
            "Should make kyma doc tool search once when no relevant documentation is found",
            KymaAgentState(
                agent_messages=[],
                messages=[
                    SystemMessage(content="{}"),
                    HumanMessage(content="What are the BTP Operator features?"),
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "id": "tool_call_id_1",
                                "type": "tool_call",
                                "name": "search_kyma_doc",
                                "args": {"query": "BTP Operator features"},
                            }
                        ],
                    ),
                    ToolMessage(
                        content="No relevant documentation found.",
                        name="search_kyma_doc",
                        tool_call_id="tool_call_id_1",
                    ),
                ],
                subtasks=[
                    {
                        "description": "What are the BTP Operator features?",
                        "task_title": "What are the BTP Operator features?",
                        "assigned_to": "KymaAgent",
                    }
                ],
                my_task=SubTask(
                    description="What are the BTP Operator features?",
                    task_title="What are the BTP Operator features?",
                    assigned_to="KymaAgent",
                ),
                k8s_client=Mock(spec_set=IK8sClient),  # noqa
                is_last_step=False,
                remaining_steps=AGENT_STEPS_NUMBER,
            ),
            "",
            "I couldn't find specific documentation on the features of the BTP Operator in the Kyma documentation. "
            "However, generally, the BTP Operator in Kyma is responsible for managing the lifecycle of "
            "SAP BTP service instances and bindings. It integrates SAP BTP services into the Kyma environment, "
            "allowing you to provision and bind services from the SAP Business Technology Platform."
            "If you have specific questions or need further details, you might want to check the official "
            "SAP BTP documentation or resources related to the BTP Operator for more comprehensive information.",
            False,
        ),
        # Test case for Kyma doc search when no relevant documentation is found
        # Serverless function deployment query
        (
            "Should search Kyma docs for serverless deployment when no relevant docs found",
            KymaAgentState(
                agent_messages=[],
                messages=[
                    SystemMessage(content="{}"),
                    HumanMessage(
                        content="What are the best practices for deploying Node.js functions in Kyma Serverless?"
                    ),
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "id": "tool_call_id_5",
                                "type": "tool_call",
                                "name": "search_kyma_doc",
                                "args": {"query": "Node.js serverless functions best practices deployment"},
                            }
                        ],
                    ),
                    ToolMessage(
                        content="No relevant documentation found.",
                        name="search_kyma_doc",
                        tool_call_id="tool_call_id_5",
                    ),
                ],
                subtasks=[
                    {
                        "description": "What are the best practices for deploying Node.js functions in Kyma Serverless?",
                        "task_title": "Node.js serverless deployment best practices",
                        "assigned_to": "KymaAgent",
                    }
                ],
                my_task=SubTask(
                    description="What are the best practices for deploying Node.js functions in Kyma Serverless?",
                    task_title="Node.js serverless deployment best practices",
                    assigned_to="KymaAgent",
                ),
                k8s_client=Mock(spec_set=IK8sClient),
                is_last_step=False,
                remaining_steps=AGENT_STEPS_NUMBER,
            ),
            "",
            "I couldn't find specific best practices documentation for Node.js functions in Kyma Serverless. "
            "However, general best practices for serverless functions in Kyma typically include: "
            "keeping functions lightweight and stateless, properly handling environment variables and secrets, "
            "implementing proper error handling and logging, setting appropriate resource limits and timeouts, "
            "and using dependency injection for external services. "
            "For Node.js specifically, consider using async/await patterns and avoiding blocking operations. "
            "Please refer to the Kyma Serverless documentation for detailed deployment guides and examples.",
            False,
        ),
        # Test case for Kyma doc search when no relevant documentation is found
        # API Gateway rate limiting query
        (
            "Should search Kyma docs for API Gateway rate limiting when no relevant docs found",
            KymaAgentState(
                agent_messages=[],
                messages=[
                    SystemMessage(content="{}"),
                    HumanMessage(content="How do I implement rate limiting in Kyma API Gateway?"),
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "id": "tool_call_id_6",
                                "type": "tool_call",
                                "name": "search_kyma_doc",
                                "args": {"query": "API Gateway rate limiting configuration"},
                            }
                        ],
                    ),
                    ToolMessage(
                        content="No relevant documentation found.",
                        name="search_kyma_doc",
                        tool_call_id="tool_call_id_6",
                    ),
                ],
                subtasks=[
                    {
                        "description": "How do I implement rate limiting in Kyma API Gateway?",
                        "task_title": "API Gateway rate limiting implementation",
                        "assigned_to": "KymaAgent",
                    }
                ],
                my_task=SubTask(
                    description="How do I implement rate limiting in Kyma API Gateway?",
                    task_title="API Gateway rate limiting implementation",
                    assigned_to="KymaAgent",
                ),
                k8s_client=Mock(spec_set=IK8sClient),
                is_last_step=False,
                remaining_steps=AGENT_STEPS_NUMBER,
            ),
            "",
            "I couldn't find specific documentation on implementing rate limiting in Kyma API Gateway. "
            "However, Kyma's API Gateway is typically built on Istio, which supports rate limiting through "
            "EnvoyFilter resources or using external rate limiting services. "
            "You can implement rate limiting by configuring Istio's rate limiting features, "
            "either through local rate limiting (using Envoy's local rate limit filter) or "
            "global rate limiting (using an external rate limit service like Redis). "
            "For detailed configuration examples, please check the Kyma API Gateway documentation "
            "or Istio's traffic management guides.",
            False,
        ),
        # Test case for healthy resource - agent should return direct answer WITHOUT calling search_kyma_doc.
        # - Resource status is Ready with no error conditions.
        # - Validates prompt rule: Do NOT call search_kyma_doc when resource is healthy.
        (
            "Should return direct answer for healthy resource without search_kyma_doc",
            KymaAgentState(
                agent_messages=[],
                messages=[
                    SystemMessage(
                        content="{'resource_kind': 'Function', 'resource_api_version': 'serverless.kyma-project.io/v1alpha2', 'resource_name': 'func1', 'resource_namespace': 'default'}"
                    ),
                    HumanMessage(content="Is the Function running correctly?"),
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "id": "tool_call_id_1",
                                "type": "tool_call",
                                "name": "kyma_query_tool",
                                "args": {
                                    "uri": "/apis/serverless.kyma-project.io/v1alpha2/namespaces/default/functions/func1"
                                },
                            }
                        ],
                    ),
                    ToolMessage(
                        content='{"apiVersion": "serverless.kyma-project.io/v1alpha2", "kind": "Function", "metadata": {"name": "func1", "namespace": "default"}, "status": {"conditions": [{"type": "Running", "status": "True", "reason": "DeploymentReady", "message": "Deployment func1 is ready"}], "state": "Ready"}}',
                        name="kyma_query_tool",
                        tool_call_id="tool_call_id_1",
                    ),
                ],
                subtasks=[
                    {
                        "description": "Is the Function running correctly?",
                        "task_title": "Is the Function running correctly?",
                        "assigned_to": "KymaAgent",
                    }
                ],
                my_task=SubTask(
                    description="Is the Function running correctly?",
                    task_title="Is the Function running correctly?",
                    assigned_to="KymaAgent",
                ),
                k8s_client=Mock(spec_set=IK8sClient),  # noqa
                is_last_step=False,
                remaining_steps=AGENT_STEPS_NUMBER,
            ),
            None,
            "The Function 'func1' is running correctly. Its state is Ready and the deployment is ready.",  # expected_result
            False,
        ),
        # Test case for a broad cluster-wide query from a clean start (no prior tool calls).
        # - Verifies agent identifies the overly broad query and responds with a clarification request
        #   WITHOUT calling any tool at all.
        # - If the agent calls a tool, response.content will be empty and GEval will score near 0.
        (
            "Should return clarification request for a broad cluster-wide query",
            KymaAgentState(
                agent_messages=[],
                messages=[
                    SystemMessage(content="{}"),
                    HumanMessage(content="What is the state of all Kyma resources in my cluster?"),
                ],
                subtasks=[
                    {
                        "description": "What is the state of all Kyma resources in my cluster?",
                        "task_title": "What is the state of all Kyma resources in my cluster?",
                        "assigned_to": "KymaAgent",
                    }
                ],
                my_task=SubTask(
                    description="What is the state of all Kyma resources in my cluster?",
                    task_title="What is the state of all Kyma resources in my cluster?",
                    assigned_to="KymaAgent",
                ),
                k8s_client=Mock(spec_set=IK8sClient),  # noqa
                is_last_step=False,
                remaining_steps=AGENT_STEPS_NUMBER,
            ),
            None,
            "I need more information to answer this question. Please provide more information about which specific resource or namespace you want to investigate.",
            False,
        ),
        # Test case for exhausted retries - agent should give up and return a best-effort answer.
        # - kyma_query_tool already failed 3 consecutive times.
        # - Verifies agent stops retrying and provides a graceful fallback response.
        (
            "Should not retry tool calling as already failed multiple times",
            KymaAgentState(
                agent_messages=[],
                messages=[
                    SystemMessage(
                        content="{'resource_kind': 'Function', 'resource_api_version': 'serverless.kyma-project.io/v1alpha2', 'resource_name': 'func1', 'resource_namespace': 'kyma-app-serverless-syntax-err'}"
                    ),
                    HumanMessage(content="what is wrong?"),
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "id": "tool_call_id_1",
                                "type": "tool_call",
                                "name": "kyma_query_tool",
                                "args": {
                                    "uri": "/apis/serverless.kyma-project.io/v1alpha2/namespaces/kyma-app-serverless-syntax-err/functions/func1"
                                },
                            }
                        ],
                    ),
                    ToolMessage(
                        content="Error : failed executing kyma_query_tool",
                        name="kyma_query_tool",
                        tool_call_id="tool_call_id_1",
                    ),
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "id": "tool_call_id_1",
                                "type": "tool_call",
                                "name": "kyma_query_tool",
                                "args": {
                                    "uri": "/apis/serverless.kyma-project.io/v1alpha2/namespaces/kyma-app-serverless-syntax-err/functions/func1"
                                },
                            }
                        ],
                    ),
                    ToolMessage(
                        content="Error : failed executing kyma_query_tool",
                        name="kyma_query_tool",
                        tool_call_id="tool_call_id_1",
                    ),
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "id": "tool_call_id_1",
                                "type": "tool_call",
                                "name": "kyma_query_tool",
                                "args": {
                                    "uri": "/apis/serverless.kyma-project.io/v1alpha2/namespaces/kyma-app-serverless-syntax-err/functions/func1"
                                },
                            }
                        ],
                    ),
                    ToolMessage(
                        content="Error : failed executing kyma_query_tool",
                        name="kyma_query_tool",
                        tool_call_id="tool_call_id_1",
                    ),
                ],
                subtasks=[
                    {
                        "description": "what is wrong with Function 'func1'?",
                        "task_title": "what is wrong with Function 'func1'?",
                        "assigned_to": "KymaAgent",
                    }
                ],
                my_task=SubTask(
                    description="what is wrong with Function 'func1'?",
                    task_title="what is wrong with Function 'func1'?",
                    assigned_to="KymaAgent",
                ),
                k8s_client=Mock(spec_set=IK8sClient),  # noqa
                is_last_step=False,
                remaining_steps=AGENT_STEPS_NUMBER,
            ),
            None,
            "I encountered an error while retrieving the information about the Function 'func1' in the namespace 'kyma-app-serverless-syntax-err'. Unfortunately, I was unable to access the necessary tools to diagnose the issue directly.",
            False,
        ),
    ],
)
@pytest.mark.asyncio
async def test_invoke_chain(
    kyma_agent,
    correctness_metric,
    faithfulness_metric,
    test_case,
    state,
    retrieval_context,
    expected_result,
    should_raise,
):
    """
    Tests answer quality: verifies the final response content using GEval (and optionally
    FaithfulnessMetric). All cases in this test produce a text answer, no tool calls.
    For tool routing tests, see test_tool_calling.
    """
    if should_raise:
        with pytest.raises(expected_result):
            await kyma_agent._invoke_chain(state, {})
    else:
        response = await kyma_agent._invoke_chain(state, {})
        assert isinstance(response, AIMessage)
        llm_test_case = LLMTestCase(
            input=state.my_task.description,
            actual_output=response.content,
            expected_output=expected_result if expected_result else None,
            retrieval_context=([retrieval_context] if retrieval_context else []),
        )
        metrics = [correctness_metric]
        if retrieval_context:
            metrics.append(faithfulness_metric)
        assert_test(llm_test_case, metrics)


@pytest.mark.parametrize(
    "test_case,state,expected_tool",
    [
        # Test case for initial APIRule query (Flow 2: api_version present → kyma_query_tool directly).
        (
            "Should return kyma_query_tool call for first query with full resource context",
            KymaAgentState(
                agent_messages=[],
                messages=[
                    SystemMessage(
                        content="{'resource_kind': 'APIRule', 'resource_api_version': 'gateway.kyma-project.io/v2', 'resource_name': 'restapi', 'resource_namespace': 'kyma-app-apirule-broken'}"
                    ),
                    HumanMessage(content="What is wrong with the APIRule?"),
                ],
                subtasks=[
                    {
                        "description": "What is wrong with the APIRule?",
                        "task_title": "What is wrong with the APIRule?",
                        "assigned_to": "KymaAgent",
                    }
                ],
                my_task=SubTask(
                    description="What is wrong with the APIRule?",
                    task_title="What is wrong with the APIRule?",
                    assigned_to="KymaAgent",
                ),
                k8s_client=Mock(spec_set=IK8sClient),  # noqa
                is_last_step=False,
                remaining_steps=AGENT_STEPS_NUMBER,
            ),
            "kyma_query_tool",
        ),
        # Test case for APIRule query with missing api_version (Flow 1: no version → discover first).
        (
            "Should return fetch_kyma_resource_version call when api_version is missing",
            KymaAgentState(
                agent_messages=[],
                messages=[
                    SystemMessage(
                        content="{'resource_kind': 'APIRule', 'resource_name': 'restapi', 'resource_namespace': 'kyma-app-apirule-broken'}"
                    ),
                    HumanMessage(content="What is wrong with the APIRule?"),
                ],
                subtasks=[
                    {
                        "description": "What is wrong with the APIRule?",
                        "task_title": "What is wrong with the APIRule?",
                        "assigned_to": "KymaAgent",
                    }
                ],
                my_task=SubTask(
                    description="What is wrong with the APIRule?",
                    task_title="What is wrong with the APIRule?",
                    assigned_to="KymaAgent",
                ),
                k8s_client=Mock(spec_set=IK8sClient),  # noqa
                is_last_step=False,
                remaining_steps=AGENT_STEPS_NUMBER,
            ),
            "fetch_kyma_resource_version",
        ),
        # Test case for kyma tool when only first tool call failed (Flow 3: error → recover via fetch version).
        (
            "Should return fetch_kyma_resource_version call to recover after first tool call failed",
            KymaAgentState(
                agent_messages=[],
                messages=[
                    SystemMessage(
                        content="{'resource_kind': 'Function', 'resource_api_version': 'serverless.kyma-project.io/v1alpha2', 'resource_name': 'func1', 'resource_namespace': 'kyma-app-serverless-syntax-err'}"
                    ),
                    HumanMessage(content="what is wrong?"),
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "id": "tool_call_id_1",
                                "type": "tool_call",
                                "name": "kyma_query_tool",
                                "args": {
                                    "uri": "/apis/serverless.kyma-project.io/v1alpha2/namespaces/kyma-app-serverless-syntax-err/functions/func1"
                                },
                            }
                        ],
                    ),
                    ToolMessage(
                        content="Error : failed executing kyma_query_tool",
                        name="kyma_query_tool",
                        tool_call_id="tool_call_id_1",
                    ),
                ],
                subtasks=[
                    {
                        "description": "what is wrong with Function 'func1'?",
                        "task_title": "what is wrong with Function 'func1'?",
                        "assigned_to": "KymaAgent",
                    }
                ],
                my_task=SubTask(
                    description="what is wrong with Function 'func1'?",
                    task_title="what is wrong with Function 'func1'?",
                    assigned_to="KymaAgent",
                ),
                k8s_client=Mock(spec_set=IK8sClient),  # noqa
                is_last_step=False,
                remaining_steps=AGENT_STEPS_NUMBER,
            ),
            "fetch_kyma_resource_version",
        ),
        # Should return use search_kyma_doc tool for Kyma question for general Kyma knowledge query
        (
            "Should return search_kyma_doc call for Kyma app creation question",
            KymaAgentState(
                agent_messages=[],
                messages=[
                    SystemMessage(content="{'resource_namespace': 'sample-ns'}"),
                    HumanMessage(content="How to create an application with Kyma and register an external service?"),
                ],
                subtasks=[
                    {
                        "description": "How to create an application with Kyma and register an external service?",
                        "task_title": "Fetching info on creating application",
                        "assigned_to": "KymaAgent",
                        "status": "pending",
                    },
                    {
                        "description": "register external service",
                        "task_title": "Fetching info on registering external service",
                        "assigned_to": "KymaAgent",
                        "status": "pending",
                    },
                ],
                my_task=SubTask(
                    description="How to create an application with Kyma and register an external service?",
                    task_title="Fetching info on creating application",
                    assigned_to="KymaAgent",
                ),
                k8s_client=Mock(spec_set=IK8sClient),  # noqa
                is_last_step=False,
                remaining_steps=AGENT_STEPS_NUMBER,
            ),
            "search_kyma_doc",
        ),
        # Should return use search_kyma_doc tool for Kyma question for general Kyma knowledge query
        (
            "Should return search_kyma_doc call for enabling a Kyma module",
            KymaAgentState(
                agent_messages=[],
                messages=[
                    SystemMessage(content="The user query is related to: {'resource_namespace': 'sample-ns'}"),
                    HumanMessage(content="How to enable a Kyma module?"),
                ],
                subtasks=[
                    {
                        "description": "How to enable a Kyma module?",
                        "task_title": "Fetching info on enabling a Kyma module",
                        "assigned_to": "KymaAgent",
                        "status": "pending",
                    },
                ],
                my_task=SubTask(
                    description="How to enable a Kyma module?",
                    task_title="Fetching info on enabling a Kyma module",
                    assigned_to="KymaAgent",
                ),
                k8s_client=Mock(spec_set=IK8sClient),  # noqa
                is_last_step=False,
                remaining_steps=AGENT_STEPS_NUMBER,
            ),
            "search_kyma_doc",
        ),
        # Should return use search_kyma_doc tool for Kyma question for general Kyma knowledge query
        (
            "Should return search_kyma_doc call for creating an APIRule",
            KymaAgentState(
                agent_messages=[],
                messages=[
                    SystemMessage(content="The user query is related to: {'resource_namespace': 'sample-ns'}"),
                    HumanMessage(content="Show how to create an API Rule"),
                ],
                subtasks=[
                    {
                        "description": "Show how to create an API Rule",
                        "task_title": "Fetching info on creating an API Rule",
                        "assigned_to": "KymaAgent",
                        "status": "pending",
                    },
                ],
                my_task=SubTask(
                    description="Show how to create an API Rule",
                    task_title="Fetching info on creating an API Rule",
                    assigned_to="KymaAgent",
                ),
                k8s_client=Mock(spec_set=IK8sClient),  # noqa
                is_last_step=False,
                remaining_steps=AGENT_STEPS_NUMBER,
            ),
            "search_kyma_doc",
        ),
    ],
)
@pytest.mark.asyncio
async def test_tool_calling(
    kyma_agent,
    test_case,
    state,
    expected_tool,
):
    """
    Tests tool routing: verifies the agent selects the correct next tool.
    All cases use assert_tool_call, no GEval.
    For answer quality tests, see test_invoke_chain.
    """
    response = await kyma_agent._invoke_chain(state, {})
    assert isinstance(response, AIMessage)
    assert_tool_call(response, expected_tool)
