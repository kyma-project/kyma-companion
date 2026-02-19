"""A2A Agent Card configuration for Kyma Companion."""

from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
)

SUPPORTED_CONTENT_TYPES = ['text', 'text/plain', 'text/event-stream']

# Agent Card: Describes the capabilities of Kyma Companion to other agents
KYMA_COMPANION_AGENT_CARD = AgentCard(
    name="Kyma Companion",
    description=(
        "An AI assistant specialized in SAP BTP Kyma Runtime and Kubernetes troubleshooting. "
        "Kyma Companion helps diagnose issues, explain configurations, "
        "and provide guidance for Kyma-based cloud-native applications."
    ),
    url="",  # Will be set dynamically based on deployment
    version="1.0.0",
    capabilities=AgentCapabilities(
        streaming=True,
        push_notifications=False,
        state_transition_history=False,
    ),
    skills=[
        AgentSkill(
            id="kyma-troubleshooting",
            name="Kyma Troubleshooting",
            description=(
                "Diagnose and resolve issues with Kyma runtime components including "
                "Functions, API Rules, Subscriptions, and other Kyma modules."
            ),
            tags=["kyma", "troubleshooting", "diagnosis", "sap"],
            examples=[
                "Why is my Kyma Function not working?",
                "Help me debug my API Rule configuration",
                "What's wrong with my eventing subscription?",
            ],
        ),
        AgentSkill(
            id="kubernetes-assistance",
            name="Kubernetes Assistance",
            description=(
                "Help with Kubernetes resources, configurations, and common issues "
                "including Pods, Deployments, Services, and other K8s objects."
            ),
            tags=["kubernetes", "k8s", "containers", "pods", "deployments"],
            examples=[
                "Why is my pod in CrashLoopBackOff?",
                "Analyze my deployment status",
                "Help me understand this Kubernetes error",
            ],
        ),
        AgentSkill(
            id="kyma-documentation",
            name="Kyma Documentation",
            description=(
                "Answer questions about Kyma concepts, best practices, "
                "and provide guidance based on official documentation."
            ),
            tags=["documentation", "concepts", "best-practices", "guidance"],
            examples=[
                "How do I configure an API Rule?",
                "What is the Kyma eventing system?",
                "Explain Kyma Functions architecture",
            ],
        ),
    ],
    default_input_modes=SUPPORTED_CONTENT_TYPES,
    default_output_modes=SUPPORTED_CONTENT_TYPES,
)


def get_agent_card(base_url: str = "") -> AgentCard:
    """
    Get the agent card with the specified base URL.
    
    Args:
        base_url: The base URL where the agent is deployed.
        
    Returns:
        The configured AgentCard.
    """
    card = KYMA_COMPANION_AGENT_CARD.model_copy()
    if base_url:
        card.url = base_url
    return card
