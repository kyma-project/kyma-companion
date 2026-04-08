
I want to merge the supervisor agent and Kyma agent into a single ReAct agent. The prompts from both agents should be merged in the best way possible. The combined agent should be called Kyma agent.

Leave the k8s agent unused for now, it will be integrated somewhere later.

The new kyma agent should have the current tools as well as the pod logs tool from the k8s agent.

The langgraph flow will that the user query will enter the Gatekeeper, the gatekeeper will take care of security attacks, prompt injections, about you and greetings queries. All the rest of the queries (either new or follow up questsions) if they are related to kyma, kubernetes, integration with SAP BTP Products and programming will be forwarded to this new kyma agent.

In future, we can add sub agents to this kyma agent along with the tools so that the kyma agent can also ultilze the sub agents for some specific tasks. Therefore, plan in such a way that it is possible.

Ignore updating the tests for now.
