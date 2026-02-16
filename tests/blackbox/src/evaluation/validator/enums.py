from enum import StrEnum


class AIModel(StrEnum):
    """Category represents enum for the category of an expectation."""

    AZURE_GPT35 = "llm_azure_gpt35-turbo"
    AZURE_GPT35_16K = "llm_azure_gpt35-turbo-16k"
    AZURE_GPT4 = "llm_azure_gpt4"
    AZURE_GPT4_32K = "llm_azure_gpt4-32k"
    CHATGPT_4_O = "gpt4.o"
    CHATGPT_4_O_MINI = "gpt-4o-mini"
    CHATGPT_4_1_MINI = "gpt-4.1-mini"
    CHATGPT_5 = "gpt-5"
    CHATGPT_5_MINI = "gpt-5-mini"
