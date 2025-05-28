import pytest
from ragas.dataset_schema import MultiTurnSample
from ragas.llms import LangchainLLMWrapper
from ragas.messages import AIMessage, HumanMessage, ToolCall, ToolMessage
from ragas.metrics import AgentGoalAccuracyWithReference

from utils.settings import MAIN_MODEL

sample = MultiTurnSample(
    user_input=[
        HumanMessage(
            content="Hey, book a table at the nearest best Chinese restaurant for 8:00pm"
        ),
        AIMessage(
            content="Sure, let me find the best options for you.",
            tool_calls=[
                ToolCall(
                    name="restaurant_search",
                    args={"cuisine": "Chinese", "time": "8:00pm"},
                )
            ],
        ),
        ToolMessage(content="Found a few options: 1. Golden Dragon, 2. Jade Palace"),
        AIMessage(
            content="I found some great options: Golden Dragon and Jade Palace. Which one would you prefer?"
        ),
        HumanMessage(content="Let's go with Golden Dragon."),
        AIMessage(
            content="Great choice! I'll book a table for 8:00pm at Golden Dragon.",
            tool_calls=[
                ToolCall(
                    name="restaurant_book",
                    args={"name": "Golden Dragon", "time": "8:00pm"},
                )
            ],
        ),
        ToolMessage(content="Table booked at Golden Dragon for 8:00pm."),
        AIMessage(
            content="Your table at Golden Dragon is booked for 8:00pm. Enjoy your meal!"
        ),
        HumanMessage(content="thanks"),
    ],
    reference="Table booked at one of the chinese restaurants at 8 pm",
)


@pytest.fixture
def evaluator_llm(app_models):
    main_model = app_models[MAIN_MODEL]
    return LangchainLLMWrapper(main_model.llm)


@pytest.fixture
def scorer(evaluator_llm):
    return AgentGoalAccuracyWithReference(llm=evaluator_llm)


@pytest.mark.asyncio
async def test_ragas_tool(scorer):
    await scorer.multi_turn_ascore(sample)
