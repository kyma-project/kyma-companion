import pytest
from ragas import MultiTurnSample
from ragas.llms import LangchainLLMWrapper
from ragas.messages import AIMessage, HumanMessage, ToolCall, ToolMessage
from ragas.metrics import AnswerAccuracy, ResponseRelevancy

from utils.settings import MAIN_MODEL


@pytest.fixture
def evaluator_llm(app_models):
    main_model = app_models[MAIN_MODEL]
    return LangchainLLMWrapper(main_model.llm)


@pytest.fixture
def response_relevancy_metric(evaluator_llm):
    # ragas metric for response relevancy
    return ResponseRelevancy(model=evaluator_llm)


@pytest.fixture
def accuracy_metric(evaluator_llm):
    return AnswerAccuracy(model=evaluator_llm)


@pytest.mark.asyncio
async def test_ragas_conversation_flow():
    # User asks about the weather in New York City
    user_message = HumanMessage(
        content="What's the weather like in New York City today?"
    )

    # AI decides to use a weather API tool to fetch the information
    ai_initial_response = AIMessage(
        content="Let me check the current weather in New York City for you.",
        tool_calls=[ToolCall(name="WeatherAPI", args={"location": "New York City"})],
    )

    # Tool provides the weather information
    tool_response = ToolMessage(
        content="It's sunny with a temperature of 75°F in New York City."
    )

    # AI delivers the final response to the user
    ai_final_response = AIMessage(
        content="It's sunny and 75 degrees Fahrenheit in New York City today."
    )

    # Combine all messages into a list to represent the conversation
    conversation = [user_message, ai_initial_response, tool_response, ai_final_response]

    # Reference response for evaluation purposes
    reference_response = "Provide the current weather in New York City to the user."

    # Create the MultiTurnSample instance
    sample = MultiTurnSample(
        user_input=conversation,
        reference=reference_response,
    )

    # Evaluate metrics
    relevancy_score = await response_relevancy_metric.multi_turn_ascore(sample)
    accuracy_score = await accuracy_metric.multi_turn_ascore(sample)

    print(f"Relevancy score: {relevancy_score}")
    print(f"Accuracy score: {accuracy_score}")
