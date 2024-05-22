from langchain.output_parsers import PydanticOutputParser, OutputFixingParser
from parser_classes import InitialQuestions
from llm_commons.langchain.proxy import ChatOpenAI


def extract_questions(llm_response: str, llm_backup: ChatOpenAI, parser: PydanticOutputParser) -> list[str]:
    questions = []
    try:
        resp_parsed: InitialQuestions = parser.parse(llm_response)
        questions = resp_parsed.improvements
        print(resp_parsed)
    except Exception as e:
        print("HANDLING AN ERROR!")
        new_parser = OutputFixingParser.from_llm(parser=parser, llm=llm_backup)
        resp_parsed: InitialQuestions = new_parser.parse(llm_response)
        questions = resp_parsed.improvements
        print(resp_parsed)
    return questions