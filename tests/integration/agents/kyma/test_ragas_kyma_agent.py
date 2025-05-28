from unittest.mock import Mock

import pytest
import ragas.messages as r
from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from ragas.dataset_schema import MultiTurnSample
from ragas.integrations.langgraph import convert_to_ragas_messages
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import AgentGoalAccuracyWithReference, ToolCallAccuracy
from tests.integration.agents.fixtures.api_rule import (
    API_RULE_WITH_WRONG_ACCESS_STRATEGY,
    EXPECTED_API_RULE_RESPONSE,
    KYMADOC_FOR_API_RULE_VALIDATION_ERROR,
)

from agents.common.state import SubTask
from agents.kyma.agent import KymaAgent
from agents.kyma.state import KymaAgentState
from services.k8s import IK8sClient
from utils.settings import MAIN_MODEL

AGENT_STEPS_NUMBER = 25


@pytest.fixture
def kyma_agent(app_models):
    return KymaAgent(app_models)


@pytest.mark.parametrize(
    "test_case,state,retrieval_context,expected_result,expected_tool_call,should_raise",
    [
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
        # Test case for kyma tool when already failed multiple times
        # and should give proper response to user,
        (
            "Should not retry tool calling as already failed multiple  times",
            KymaAgentState(
                agent_messages=[],
                messages=[
                    SystemMessage(
                        content="The user query is related to: "
                        "{'resource_kind': 'Function', "
                        "'resource_api_version': 'serverless.kyma-project.io/v1alpha2', "
                        "'resource_name': 'func1', "
                        "'resource_namespace': 'kyma-app-serverless-syntax-err'}"
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
                                    "uri": "/apis/serverless.kyma-project.io/v1alpha2/"
                                    "namespaces/kyma-app-serverless-syntax-err/functions/func1"
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
                                    "uri": "/apis/serverless.kyma-project.io/v1alpha2/"
                                    "namespaces/kyma-app-serverless-syntax-err/functions/func1"
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
                                    "uri": "/apis/serverless.kyma-project.io/v1alpha2/"
                                    "namespaces/kyma-app-serverless-syntax-err/functions/func1"
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
                        content="""I encountered an error while retrieving the information about the Function 'func1' in the namespace 'kyma-app-serverless-syntax-err'. Unfortunately, I was unable to access the necessary tools to diagnose the issue directly.

To troubleshoot the problem with your Kyma Function, you can consider the following general steps:

1. **Check Logs**: Look at the logs of the Function to see if there are any error messages that can provide more context. You can do this by using `kubectl logs` command.

2. **Inspect the Function Resource**: Use `kubectl describe function func1 -n kyma-app-serverless-syntax-err` to get detailed information about the Function, including events that might indicate what went wrong.

3. **Validate the YAML Configuration**: Ensure that the YAML configuration for the Function is correct. Common issues include syntax errors, incorrect runtime settings, or missing dependencies.

4. **Check Dependencies**: If your Function relies on external services or APIs, ensure that they are accessible and functioning correctly.

5. **Resource Quotas**: Verify that there are no resource quota issues in the namespace that might be preventing the Function from running.

If you continue to experience issues, you may want to consult the Kyma documentation or seek support from the Kyma community for more specific guidance.
                        """
                    ),
                ],
                subtasks=[
                    {
                        "description": "What is wrong with Function 'func1' in namespace "
                        "'kyma-app-serverless-syntax-err' with api version "
                        "'serverless.kyma-project.io/v1alpha2'?",
                        "task_title": "What is wrong with Function 'func1' in namespace "
                        "'kyma-app-serverless-syntax-err' with api version "
                        "'serverless.kyma-project.io/v1alpha2'?",
                        "assigned_to": "KymaAgent",
                    }
                ],
                my_task=SubTask(
                    description="What is wrong with Function 'func1' in namespace "
                    "'kyma-app-serverless-syntax-err' with api version "
                    "'serverless.kyma-project.io/v1alpha2'?",
                    task_title="What is wrong with Function 'func1' in namespace "
                    "'kyma-app-serverless-syntax-err' with api version "
                    "'serverless.kyma-project.io/v1alpha2'?",
                    assigned_to="KymaAgent",
                ),
                k8s_client=Mock(spec_set=IK8sClient),  # noqa
                is_last_step=False,
                remaining_steps=AGENT_STEPS_NUMBER,
            ),  # context
            None,  # retrieval_context
            """I encountered an error while retrieving the information about the Function 'func1' in the namespace 'kyma-app-serverless-syntax-err'. Unfortunately, I was unable to access the necessary tools to diagnose the issue directly.

To troubleshoot the problem with your Kyma Function, you can consider the following general steps:

1. **Check Logs**: Look at the logs of the Function to see if there are any error messages that can provide more context. You can do this by using `kubectl logs` command.

2. **Inspect the Function Resource**: Use `kubectl describe function func1 -n kyma-app-serverless-syntax-err` to get detailed information about the Function, including events that might indicate what went wrong.

3. **Validate the YAML Configuration**: Ensure that the YAML configuration for the Function is correct. Common issues include syntax errors, incorrect runtime settings, or missing dependencies.

4. **Check Dependencies**: If your Function relies on external services or APIs, ensure that they are accessible and functioning correctly.

5. **Resource Quotas**: Verify that there are no resource quota issues in the namespace that might be preventing the Function from running.

If you continue to experience issues, you may want to consult the Kyma documentation or seek support from the Kyma community for more specific guidance.""",  # expected_result
            None,  # expected_tool_call
            False,  # should_raise
        ),
    ],
)
@pytest.mark.asyncio
async def test_tool_calling(
    kyma_agent,
    app_models,
    test_case,
    state,
    retrieval_context,
    expected_result,
    expected_tool_call,
    should_raise,
):
    """
    Tests that the _invoke_chain method of the KymaAgent returns the expected response
    for the given user query, subtask and tool calls using RAGAS evaluation.
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

            # Additional RAGAS evaluation for tool calls
            # Convert messages to RAGAS format
            all_messages = list(state.messages) + [response]
            ragas_messages = convert_to_ragas_messages(all_messages)

            # Create MultiTurnSample for tool call accuracy
            sample = MultiTurnSample(
                user_input=ragas_messages,
                reference_tool_calls=[r.ToolCall(name=expected_tool_call, args={})],
            )

            # Evaluate tool call accuracy
            tool_accuracy_scorer = ToolCallAccuracy()
            tool_accuracy_scorer.llm = LangchainLLMWrapper(app_models[MAIN_MODEL].llm)
            score = await tool_accuracy_scorer.multi_turn_ascore(sample)

            # Assert that tool call accuracy is high (>= 0.8)
            assert score >= 0.8, f"Tool call accuracy too low: {score}"

        else:
            # for content response cases, verify using RAGAS metrics
            if expected_result and expected_result.strip():
                # Convert messages to RAGAS format
                all_messages = list(state.messages) + [response]
                ragas_messages = convert_to_ragas_messages(all_messages)

                # Create MultiTurnSample for agent goal accuracy
                sample = MultiTurnSample(
                    user_input=ragas_messages,
                    reference=expected_result,
                )

                # Evaluate agent goal accuracy
                goal_accuracy_scorer = AgentGoalAccuracyWithReference()
                goal_accuracy_scorer.llm = LangchainLLMWrapper(
                    app_models[MAIN_MODEL].llm
                )
                score = await goal_accuracy_scorer.multi_turn_ascore(sample)

                # Assert that goal accuracy is high (>= 0.7)
                assert score >= 0.7, f"Agent goal accuracy too low: {score}"
