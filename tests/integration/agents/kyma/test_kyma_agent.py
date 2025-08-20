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
    API_RULE_WITH_WRONG_ACCESS_STRATEGY,
    EXPECTED_API_RULE_RESPONSE,
    EXPECTED_API_RULE_TOOL_CALL_RESPONSE,
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


@pytest.fixture
def mock_k8s_client():
    return Mock(spec_set=IK8sClient)


@pytest.fixture
def kyma_agent(app_models):
    return KymaAgent(app_models)


@pytest.mark.parametrize(
    "test_case,state,retrieval_context,expected_result,expected_tool_call,should_raise",
    [
        # Test case for API Rule with wrong access strategy
        # - Verifies agent correctly identifies and explains API Rule validation error
        # - Checks agent uses both kyma_query_tool and search_kyma_doc
        # - Validates response matches expected explanation about multiple access strategies
        # Security configuration query
        (
            "Should search Kyma docs for security configuration when no relevant docs found",
            KymaAgentState(
                agent_messages=[],
                messages=[
                    SystemMessage(content="The user query is related to: {}"),
                    HumanMessage(
                        content="How do I configure OAuth2 authentication in Kyma?"
                    ),
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "id": "tool_call_id_2",
                                "type": "tool_call",
                                "name": "search_kyma_doc",
                                "args": {
                                    "query": "OAuth2 authentication configuration Kyma"
                                },
                            }
                        ],
                    ),
                    ToolMessage(
                        content="No relevant documentation found.",
                        name="search_kyma_doc",
                        tool_call_id="tool_call_id_2",
                    ),
                ],
                subtasks=[
                    {
                        "description": "How do I configure OAuth2 authentication in Kyma?",
                        "task_title": "OAuth2 authentication configuration",
                        "assigned_to": "KymaAgent",
                    }
                ],
                my_task=SubTask(
                    description="How do I configure OAuth2 authentication in Kyma?",
                    task_title="OAuth2 authentication configuration",
                    assigned_to="KymaAgent",
                ),
                k8s_client=Mock(spec_set=IK8sClient),
                is_last_step=False,
                remaining_steps=AGENT_STEPS_NUMBER,
            ),
            "",
            "I couldn't find specific documentation on OAuth2 authentication configuration in the Kyma documentation. "
            "However, Kyma typically uses Istio's authentication and authorization features for securing applications. "
            "You would generally configure OAuth2 through Istio's RequestAuthentication and AuthorizationPolicy resources, "
            "or by using the Kyma API Gateway with OAuth2 introspection. "
            "For detailed configuration steps, I recommend checking the official Kyma security documentation "
            "or the Istio authentication documentation.",
            None,
            False,
        ),
        (
            "Should return right solution for API Rule with wrong access strategy",
            KymaAgentState(
                agent_messages=[],
                messages=[
                    SystemMessage(
                        content="The user query is related to: {'resource_api_version': 'gateway.kyma-project.io/v1beta1', 'resource_namespace': 'kyma-app-apirule-broken'}"
                    ),
                    HumanMessage(content="What is wrong with api rule?"),
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "id": "tool_call_id_1",
                                "type": "tool_call",
                                "name": "kyma_query_tool",
                                "args": {
                                    "uri": "/apis/gateway.kyma-project.io/v1beta1/namespaces/kyma-app-apirule-broken/apirules"
                                },
                            }
                        ],
                    ),
                    ToolMessage(
                        content=API_RULE_WITH_WRONG_ACCESS_STRATEGY,
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
                        "description": "What is wrong with ApiRule?",
                        "task_title": "What is wrong with ApiRule?",
                        "assigned_to": "KymaAgent",
                    }
                ],
                my_task=SubTask(
                    description="What is wrong with API rule?",
                    task_title="What is wrong with API rule?",
                    assigned_to="KymaAgent",
                ),
                k8s_client=Mock(spec_set=IK8sClient),
                is_last_step=False,
                remaining_steps=AGENT_STEPS_NUMBER,
            ),
            KYMADOC_FOR_API_RULE_VALIDATION_ERROR,
            EXPECTED_API_RULE_RESPONSE,
            None,
            False,
        ),
        # Test case for initial API Rule query
        # - Verifies agent makes correct kyma_query_tool call on first interaction
        (
            "Should return Kyma resource query tool call for the first user query call",
            KymaAgentState(
                agent_messages=[],
                messages=[
                    SystemMessage(
                        content="The user query is related to: {'resource_api_version': 'gateway.kyma-project.io/v1beta1', 'resource_namespace': 'kyma-app-apirule-broken'}"
                    ),
                    HumanMessage(content="What is wrong with api rule?"),
                ],
                subtasks=[
                    {
                        "description": "What is wrong with ApiRule?",
                        "task_title": "What is wrong with ApiRule?",
                        "assigned_to": "KymaAgent",
                    }
                ],
                my_task=SubTask(
                    description="What is wrong with api rule?",
                    task_title="What is wrong with api rule?",
                    assigned_to="KymaAgent",
                ),
                k8s_client=Mock(spec_set=IK8sClient),  # noqa
                is_last_step=False,
                remaining_steps=AGENT_STEPS_NUMBER,
            ),
            None,
            EXPECTED_API_RULE_TOOL_CALL_RESPONSE,
            "kyma_query_tool",
            False,
        ),
        # Test case for API Rule documentation search
        # - Verifies agent searches Kyma docs after getting API Rule resource
        # - Validates proper sequence of tool calls (query then doc search)
        (
            "Should return Kyma Doc Search Tool Call after Kyma Resource Query Tool Call",
            KymaAgentState(
                agent_messages=[],
                messages=[
                    SystemMessage(
                        content="The user query is related to: {'resource_api_version': 'gateway.kyma-project.io/v1beta1', 'resource_namespace': 'kyma-app-apirule-broken'}"
                    ),
                    HumanMessage(content="What is wrong with api rule?"),
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "id": "tool_call_id_1",
                                "type": "tool_call",
                                "name": "kyma_query_tool",
                                "args": {
                                    "uri": "/apis/gateway.kyma-project.io/v1beta1/namespaces/kyma-app-apirule-broken/apirules"
                                },
                            }
                        ],
                    ),
                    ToolMessage(
                        content=API_RULE_WITH_WRONG_ACCESS_STRATEGY,
                        name="kyma_query_tool",
                        tool_call_id="tool_call_id_1",
                    ),
                ],
                subtasks=[
                    {
                        "description": "What is wrong with ApiRule?",
                        "task_title": "What is wrong with ApiRule?",
                        "assigned_to": "KymaAgent",
                    }
                ],
                my_task=SubTask(
                    description="What is wrong with ApiRule?",
                    task_title="What is wrong with ApiRule?",
                    assigned_to="KymaAgent",
                ),
                k8s_client=Mock(spec_set=IK8sClient),  # noqa
                is_last_step=False,
                remaining_steps=AGENT_STEPS_NUMBER,
            ),
            None,
            EXPECTED_API_RULE_TOOL_CALL_RESPONSE,
            "search_kyma_doc",
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
                        content="The user query is related to: {'resource_kind': 'Function', 'resource_api_version': 'serverless.kyma-project.io/v1alpha2', 'resource_name': 'func1', 'resource_namespace': 'kyma-app-serverless-syntax-err'}"
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
            None,  # expected_tool_call
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
                    SystemMessage(
                        content="The user query is related to: {'resource_namespace': 'kyma-serverless-function-no-replicas'}"
                    ),
                    HumanMessage(
                        content="Why is the pod of the serverless Function not ready?"
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
            None,
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
                    SystemMessage(content="The user query is related to: {}"),
                    HumanMessage(content="what are the BTP Operator features?"),
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
                        "description": "what are the BTP Operator features?",
                        "task_title": "what are the BTP Operator features?",
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
            None,
            False,
        ),
        # Test case for Kyma doc search when no relevant documentation is found
        # - it still responds with the existing knowledge as BTP Operator features are known to LLM
        (
            "Should make kyma doc tool search once when no relevant documentation is found",
            KymaAgentState(
                agent_messages=[],
                messages=[
                    SystemMessage(content="The user query is related to: {}"),
                    HumanMessage(content="what are the BTP Operator features?"),
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
                        "description": "what are the BTP Operator features?",
                        "task_title": "what are the BTP Operator features?",
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
            None,
            False,
        ),
        # Test case for Kyma doc search when no relevant documentation is found
        # Test case for Kyma doc search when no relevant documentation is found
        # Serverless function deployment query
        (
            "Should search Kyma docs for serverless deployment when no relevant docs found",
            KymaAgentState(
                agent_messages=[],
                messages=[
                    SystemMessage(content="The user query is related to: {}"),
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
                                "args": {
                                    "query": "Node.js serverless functions best practices deployment"
                                },
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
            None,
            False,
        ),
        # Test case for Kyma doc search when no relevant documentation is found
        # API Gateway rate limiting query
        (
            "Should search Kyma docs for API Gateway rate limiting when no relevant docs found",
            KymaAgentState(
                agent_messages=[],
                messages=[
                    SystemMessage(content="The user query is related to: {}"),
                    HumanMessage(
                        content="How do I implement rate limiting in Kyma API Gateway?"
                    ),
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "id": "tool_call_id_6",
                                "type": "tool_call",
                                "name": "search_kyma_doc",
                                "args": {
                                    "query": "API Gateway rate limiting configuration"
                                },
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
            None,
            False,
        ),
        (
            "Should mention about Joule context in kyma dashboard",
            KymaAgentState(
                agent_messages=[],
                messages=[
                    SystemMessage(
                        content="The user query is related to: {'resource_kind': 'Function', 'resource_api_version': 'serverless.kyma-project.io/v1alpha2'}"
                    ),
                    HumanMessage(
                        content="Why is the pod of the serverless Function not ready?"
                    ),
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "id": "tool_call_id_1",
                                "type": "tool_call",
                                "name": "kyma_query_tool",
                                "args": {
                                    "uri": "/apis/serverless.kyma-project.io/v1alpha2/functions"
                                },
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
            "I need more information to answer this question. Please provide the name and namespace of the Function whose pod is not ready. This will help me investigate the specific issue and provide a solution tailored to your resource. "
            "Joule enhances your workflow by using the active resource in your Kyma dashboard as the context for your queries. This ensures that when you ask questions, Joule delivers relevant and tailored answers specific to the resource you're engaged with, making your interactions both efficient and intuitive.",
            None,
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
    expected_tool_call,
    should_raise,
):
    """
    Tests that the _invoke_chain method of the KymaAgent returns the expected response
    for the given user query, subtask and tool calls.
    """
    # Given: A KymaAgent instance and test parameters

    if should_raise:
        # When: the chain is invoked and an error is expected
        # Then: the expected error should be raised
        with pytest.raises(expected_result):
            kyma_agent._invoke_chain(state, {})
    else:
        # When: the chain is invoked normally
        response = await kyma_agent._invoke_chain(state, {})
        assert isinstance(response, AIMessage)

        # Then: Verify the response based on expected behavior
        if expected_tool_call:
            # for tool call cases, verify tool call properties
            assert response.tool_calls is not None, "Expected tool calls but found none"
            assert len(response.tool_calls) > 0, "Expected at least one tool call"
            tool_call = response.tool_calls[0]
            assert tool_call.get("type") == "tool_call"
            assert tool_call.get("name") == expected_tool_call
        else:
            # for content response cases, verify using deepeval metrics
            test_case = LLMTestCase(
                input=state.my_task.description,
                actual_output=response.content,
                expected_output=expected_result if expected_result else None,
                retrieval_context=([retrieval_context] if retrieval_context else []),
            )
            # evaluate if the gotten response is semantically similar and faithful to the expected response
            assert_test(test_case, [correctness_metric, faithfulness_metric])


@pytest.mark.parametrize(
    "test_case,state,retrieval_context,expected_result,expected_tool_call,should_raise",
    [
        # Test case for kyma tool when already failed multiple times
        # and should give proper response to user,
        (
            "Should not retry tool calling as already failed multiple  times",
            KymaAgentState(
                agent_messages=[],
                messages=[
                    SystemMessage(
                        content="The user query is related to: {'resource_kind': 'Function', 'resource_api_version': 'serverless.kyma-project.io/v1alpha2', 'resource_name': 'func1', 'resource_namespace': 'kyma-app-serverless-syntax-err'}"
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
            """I encountered an error while retrieving the information about the Function 'func1' in the namespace 'kyma-app-serverless-syntax-err'. Unfortunately, I was unable to access the necessary tools to diagnose the issue directly.

<SOME TROUBLESHOOTING TIPS HERE>""",  # expected_result
            None,  # expected_tool_call
            False,  # should_raise
        ),
        # Test case for kyma tool when only first tool call failed and should retry tool calling.
        (
            "Should retry tool calling after first tool call failed",
            KymaAgentState(
                agent_messages=[],
                messages=[
                    SystemMessage(
                        content="The user query is related to: {'resource_kind': 'Function', 'resource_api_version': 'serverless.kyma-project.io/v1alpha2', 'resource_name': 'func1', 'resource_namespace': 'kyma-app-serverless-syntax-err'}"
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
            "",  # expected_result
            "fetch_kyma_resource_version",  # expected_tool_call
            False,  # should_raise
        ),
        # Should return use search_kyma_doc tool for Kyma question for general Kyma knowledge query
        (
            "Should return use search_kyma_doc tool for Kyma question",
            KymaAgentState(
                agent_messages=[],
                messages=[
                    SystemMessage(
                        content="The user query is related to: {'resource_namespace': 'sample-ns'}"
                    ),
                    HumanMessage(
                        content="how to create an application with Kyma and register external service"
                    ),
                ],
                subtasks=[
                    {
                        "description": "how to create an application with Kyma",
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
                    description="how to create an application with Kyma",
                    task_title="Fetching info on creating application",
                    assigned_to="KymaAgent",
                ),
                k8s_client=Mock(spec_set=IK8sClient),  # noqa
                is_last_step=False,
                remaining_steps=AGENT_STEPS_NUMBER,
            ),  # context
            None,  # retrieval_context
            "",  # expected_result
            "search_kyma_doc",  # expected_tool_call
            False,  # should_raise
        ),
        # Should return use search_kyma_doc tool for Kyma question for general Kyma knowledge query
        (
            "Should return use search_kyma_doc tool for Kyma question",
            KymaAgentState(
                agent_messages=[],
                messages=[
                    SystemMessage(
                        content="The user query is related to: {'resource_namespace': 'sample-ns'}"
                    ),
                    HumanMessage(content="how to enable a Kyma module?"),
                ],
                subtasks=[
                    {
                        "description": "how to enable a Kyma module?",
                        "task_title": "Fetching info on enabling a Kyma module",
                        "assigned_to": "KymaAgent",
                        "status": "pending",
                    },
                ],
                my_task=SubTask(
                    description="how to enable a Kyma module?",
                    task_title="Fetching info on enabling a Kyma module",
                    assigned_to="KymaAgent",
                ),
                k8s_client=Mock(spec_set=IK8sClient),  # noqa
                is_last_step=False,
                remaining_steps=AGENT_STEPS_NUMBER,
            ),  # context
            None,  # retrieval_context
            "",  # expected_result
            "search_kyma_doc",  # expected_tool_call
            False,  # should_raise
        ),
        # Should return use search_kyma_doc tool for Kyma question for general Kyma knowledge query
        (
            "Should return use search_kyma_doc tool for Kyma question",
            KymaAgentState(
                agent_messages=[],
                messages=[
                    SystemMessage(
                        content="The user query is related to: {'resource_namespace': 'sample-ns'}"
                    ),
                    HumanMessage(content="show how to create an API Rule"),
                ],
                subtasks=[
                    {
                        "description": "show how to create an API Rule",
                        "task_title": "Fetching info on creating an API Rule",
                        "assigned_to": "KymaAgent",
                        "status": "pending",
                    },
                ],
                my_task=SubTask(
                    description="show how to create an API Rule",
                    task_title="Fetching info on creating an API Rule",
                    assigned_to="KymaAgent",
                ),
                k8s_client=Mock(spec_set=IK8sClient),  # noqa
                is_last_step=False,
                remaining_steps=AGENT_STEPS_NUMBER,
            ),  # context
            None,  # retrieval_context
            "",  # expected_result
            "search_kyma_doc",  # expected_tool_call
            False,  # should_raise
        ),
    ],
)
@pytest.mark.asyncio
async def test_tool_calling(
    kyma_agent,
    correctness_metric,
    faithfulness_metric,
    test_case,
    state,
    retrieval_context,
    expected_result,
    expected_tool_call,
    should_raise,
):
    """
    Tests that the _invoke_chain method of the KymaAgent returns the expected response
    for the given user query, subtask and tool calls.
    """
    # Given: A KymaAgent instance and test parameters

    if should_raise:
        # When: the chain is invoked and an error is expected
        # Then: the expected error should be raised
        with pytest.raises(expected_result):
            await kyma_agent._invoke_chain(state, {})
    else:
        # When: the chain is invoked normally
        response = await kyma_agent._invoke_chain(state, {})
        assert isinstance(response, AIMessage)

        # Then: Verify the response based on expected behavior
        if expected_tool_call:
            # for tool call cases, verify tool call properties
            assert response.tool_calls is not None, "Expected tool calls but found none"
            assert len(response.tool_calls) > 0, "Expected at least one tool call"
            tool_call = response.tool_calls[0]
            assert tool_call.get("type") == "tool_call"
            assert tool_call.get("name") == expected_tool_call
        else:
            # for content response cases, verify using deepeval metrics
            test_case = LLMTestCase(
                input=state.my_task.description,
                actual_output=response.content,
                expected_output=expected_result if expected_result else None,
                retrieval_context=([retrieval_context] if retrieval_context else []),
            )
            # evaluate if the gotten response is semantically similar and faithful to the expected response
            assert_test(test_case, [correctness_metric, faithfulness_metric])
