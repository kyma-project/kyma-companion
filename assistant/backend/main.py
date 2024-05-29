import json
from langchain.prompts import PromptTemplate
from langchain.output_parsers import PydanticOutputParser
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain.chains import LLMChain
from openai import BadRequestError
from flask_cors import CORS
import subprocess
import os
from flow_functions import extract_questions
from flow_templates import GENERATE_INITIAL_QUESTIONS, FOLLOW_UP_QUESTIONS
from parser_classes import InitialQuestions
from flask import Flask, Response, request, jsonify
from agents.agent_utils import create_assistant_agent
from agents.agent_utils import generate_streaming_output
from helpers.models import create_model, LLM_AZURE_GPT35
from helpers.k8s_resources import (extract_resource_names, extract_namespace_scoped_resources,
                                   extract_all_api_resources)
from langchain_core.runnables.history import RunnableWithMessageHistory
from llm_commons.langchain.proxy import ChatOpenAI
from langchain_community.chat_message_histories import RedisChatMessageHistory
from agents.chat import AISession


# Moved creation of Flask application object into a function
def create_app():
    app = Flask(__name__)
    CORS(app)
    return app


# Call the function to create the 'app' object
app = create_app()

my_env = os.environ.copy()

questions_parser = PydanticOutputParser(pydantic_object=InitialQuestions)

g = {}


class LLMHandler:
    def __init__(self):
        self.sessions: dict[str, AISession] = {}

    def get_or_create_session(self, session_id: str, namespace: str = "") -> AISession:
        session = self.sessions.get(session_id)
        if session is None:
            session = AISession(session_id, namespace=namespace)
            self.sessions[session_id] = session
        return session
    
    def initialize_session(self, session_id: str, namespace: str):
        session = self.get_or_create_session(session_id, namespace)
        if session.namespace != namespace:
            session.agent = create_assistant_agent(session.history, namespace)
            self.sessions[session_id] = session

    def initialize_user_history(self, session_id: str, resource_context: str) -> ChatMessageHistory:
        history = self.get_or_create_session(session_id).history
        history.clear()
        history.add_user_message(
            """
                Those are the resources I initially got before asking you a question. Remember them:
            """
            + resource_context
        )
        history.add_ai_message("Got it!")

    def handle_question(self, question: str, session_id: str):
        agent = self.get_or_create_session(session_id).agent

        query = question
        try:
            for chunk in agent.stream(
                    {
                        "input": query,
                    },
                    config={"configurable": {"session_id": session_id}},
            ):
                yield generate_streaming_output(chunk) + "\n"
        except BadRequestError as e:
            print(e)
            yield json.dumps(
                {"error": "You exceeded the number of tokens during the request to LLM"}
            )
        except GeneratorExit:
            # Handle what happens if the connection is closed
            app.logger.debug("Connection closed")
            pass
        except Exception as e:
            app.logger.error("Error during streaming: %s", str(e))
            yield json.dumps({"error": "Internal server error during streaming"})

    def generate_follow_up_questions(self, session_id: str) -> list[str]:
        session = self.get_or_create_session(session_id)

        prompt = PromptTemplate(
            template=FOLLOW_UP_QUESTIONS,
            input_variables=["context", "format_instructions"],
        )

        llm_chain = LLMChain(
            prompt=prompt.partial(
                context=self.get_or_create_session(session_id).history,
                format_instructions=questions_parser.get_format_instructions()
            ),
            llm=session.follow_up_questions_model,
            verbose=True,
        )
        model_response = llm_chain.predict()
        questions = extract_questions(
            model_response, session.follow_up_questions_model, questions_parser
        )
        return questions

    def generate_initial_questions(self, session_id, resource_context) -> list[str]:
        session = self.get_or_create_session(session_id)
        
        prompt = PromptTemplate(
            template=GENERATE_INITIAL_QUESTIONS,
            input_variables=["question"],
            partial_variables={
                "format_instructions": questions_parser.get_format_instructions(),
                "context": resource_context,
            },
        )
        llm_chain = LLMChain(
            prompt=prompt, llm=session.init_questions_model, verbose=True
        )
        model_response = llm_chain.predict()
        questions = extract_questions(
            model_response, session.init_questions_model, questions_parser
        )
        return questions


handler: LLMHandler = LLMHandler()
g["handler"] = handler


# API
@app.route("/api/v1/llm/init", methods=["POST"])
def init_llm():
    """
    This function returns initial questions about a given kubernetes resource.
    Returns:
    flask.Response: Initial questions
    """

    # get data input from frontend
    data = request.get_json()
    resource_type = data.get("resource_type")
    resource_name = data.get("resource_name")
    namespace = ""
    if data.get("namespace"):
        namespace = data.get("namespace")
    elif data.get("resource_type") == "namespace":
        namespace = data.get("resource_name")
    session_id = data.get("session_id")

    # create the `kubectl` command for the given resource
    # define conditions
    is_cluster_scoped_resource = namespace == "" and resource_type != ""
    is_namespace_scoped_resource = namespace != "" and resource_type != ""
    is_namespace_overview = namespace == "" and resource_type == "namespace"
    is_cluster_overview = namespace == "" and resource_type == "cluster"

    pages_commands = []
    if is_cluster_overview:
        # cluster overview
        pages_commands.append(
            "kubectl get pods --all-namespaces --field-selector=status.phase!=Running"
        )
        pages_commands.append("kubectl top nodes")
        pages_commands.append("kubectl get events -A | grep 'Warning'")
    elif is_namespace_overview:
        # namespace overview
        pages_commands.append(f"kubectl get events -n {resource_name} | grep 'Warning'")
    elif is_cluster_scoped_resource:
        # cluster-scoped detail view
        pages_commands.append(f"kubectl describe {resource_type} {resource_name}")
        pages_commands.append(f"kubectl get events -A | grep {resource_name}")
    elif is_namespace_scoped_resource:
        # namespace-scoped detail view
        pages_commands.append(
            f"kubectl -n {namespace} describe {resource_type} {resource_name}"
        )
        pages_commands.append(
            f"kubectl get events -n {namespace} | grep {resource_name}"
        )

    # runs the `kubectl get` command related to the selected kubernetes resource
    resource_context = ""
    for command in pages_commands:
        try:
            resource_context = "\n".join(
                [
                    resource_context,
                    subprocess.check_output(
                        command,
                        shell=True,
                        text=True,
                        env=my_env,
                        stderr=subprocess.STDOUT,
                    ),
                ]
            )
            resource_context = "\n".join(
                [
                    resource_context,
                    f"Command:\n{command}\n\nResource:\n{resource_context}",
                ]
            )
        except subprocess.CalledProcessError as e:
            error = e.output
            app.logger.debug("Kubectl command returned an Error: %s", error)
            if error != "":
                resource_context = "\n".join(
                    [resource_context, f"Command:\n{command}\n\nError:\n{error}"]
                )

    g["handler"].initialize_session(session_id, namespace)
    g["handler"].initialize_user_history(session_id, resource_context)

    initial_questions = g["handler"].generate_initial_questions(
        session_id, resource_context
    )
    app.logger.info("%s", "Here are some questions you may want to ask the model:")
    for question in initial_questions:
        app.logger.info("%s", question)

    return jsonify({"results": initial_questions})


@app.route("/api/v1/chat", methods=["POST"])
def chat():
    data = request.get_json()
    question = data.get("question")
    session_id = data.get("session_id")

    return Response(
        g["handler"].handle_question(question, session_id), mimetype="application/json"
    )


@app.route("/api/v1/llm/followup", methods=["POST"])
def create_follow_up_questions():
    """
    This function returns follow-up questions according to the previous context.
    Returns:
    flask.Response: Follow-up questions
    """

    data = request.get_json()
    session_id = data.get("session_id")

    follow_up_questions = g["handler"].generate_follow_up_questions(session_id)
    app.logger.info("Possible follow-up questions: %s", follow_up_questions)

    return jsonify({"results": follow_up_questions})


# Currently, this function is used to provide the user in the UI with a list of kubernetes resources.
# Once the assistant is integrated in the UI, this function will not be needed in this way,
# as the frontend will provide `namespace`, `resourceType` and `resourceName` depending on the current context.
@app.route("/api/v1/resources", methods=["GET"])
def get_all_resources():
    """
    This function fetches all the available kubernetes resources in the cluster.
    Returns:
    flask.Response: list of available kubernetes resources
    """
    # get parameters from request
    namespaced = request.args.get("namespaced", "false")
    if namespaced == "true":
        resources = extract_namespace_scoped_resources(my_env)
    else:
        resources = extract_all_api_resources(my_env)

    return jsonify({"results": resources})


# This function is a helper function to work with the simplified VUE UI. This is not needed for the
# Busola frontend.
@app.route("/api/v1/resourceNames", methods=["GET"])
def get_all_resourceNames():
    """
    This function fetches all the resource names per given resource type.
    Returns:
    flask.Respnse: list of resource names per resource type
    """
    # get data input from frontend
    resourceType = request.args.get("resourceType")
    namespace = request.args.get("namespace")

    resourceNames = extract_resource_names(resourceType, namespace, my_env)

    return jsonify({"results": resourceNames})

@app.route("/api/v1/health/check", methods=["GET"])
def health_check():
    """
    This function is used to check the health of the backend service.
    Returns:
    flask.Response: health status
    """
    return jsonify({"status": "healthy"})

if __name__ == "__main__":
    # DEV mode
    app.run(debug=True)

    # PROD mode
    # from waitress import serve
    # serve(app, host="0.0.0.0", port=8090)
