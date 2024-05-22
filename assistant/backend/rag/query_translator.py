from typing import Protocol
import re

from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from .prompt_templates import PROMPT_TEMPLATE_HYDE, PROMPT_TEMPLATE_MULT_QUERY
from .kyma_resource_names import KYMA_RESOURCE_NAMES


class QueryTranslator(Protocol):
    def transform(self, query: str, context: str) -> str:
        ...


class HydeTranslator:
    def __init__(self, llm):
        self.llm = llm

    def transform(self, query: str, context: str) -> str:
        """
        Transforms the query into a hypothetical document that answers the query by considering the context.
        Args:
            query (str): The query to be transformed.
            context (str): The context to consider when transforming the query.
        Returns:
            str: The hypothetical document that answers the query.
        """

        hyde_prompt = build_prompt(query, context, PROMPT_TEMPLATE_HYDE)

        chain_hyde = LLMChain(prompt=hyde_prompt, llm=self.llm, verbose=True)

        hypothetical_doc = chain_hyde.invoke({
            "question": query
        })['text']
        print(f"hypothetical doc: {hypothetical_doc}")
        return hypothetical_doc


class MultiQueryTranslator:
    def __init__(self, llm):
        self.llm = llm

    def transform(self, query: str, context: str) -> str:
        """
        Transforms the query to multiple queries by considering the context.
        Args:
            query (str): The query to be transformed.
            context (str): The context to consider when transforming the query.
        Returns:
            str: multiple queries as separate lines.
        """

        multi_query_prompt = build_prompt(context, PROMPT_TEMPLATE_MULT_QUERY)

        chain = LLMChain(prompt=multi_query_prompt, llm=self.llm, verbose=True)
        multi_query = chain.invoke({
            "question": query
        })['text']
        print(f"multi query: {multi_query}")
        return multi_query


def build_prompt(resource: str, prompt_template: str):
    # uses the resource content if it is a Kyma resource
    return PromptTemplate(
        template=prompt_template,
        input_variables=["question"],
        partial_variables={
            "context": resource if is_kyma_resource(resource) else "",
        })


def is_kyma_resource(resource: str) -> bool:
    pattern = r"Kind:\s*(.+)"
    match = re.search(pattern, resource, re.MULTILINE)

    if match:
        kind = match.group(1)
        return kind in KYMA_RESOURCE_NAMES
    else:
        return False
