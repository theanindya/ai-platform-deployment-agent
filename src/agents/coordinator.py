from google.adk.workflow import Workflow, START
from src.agents.security import security_compliance_agent
from src.agents.quality import model_quality_agent
from src.agents.infrastructure import infrastructure_readiness_agent
from src.agents.risk_assessment import risk_assessment_agent
from src.agents.policy_decision import policy_decision_agent

# Define the ADK workflow representing the orchestrator
DeploymentCoordinatorAgent = Workflow(
    name="DeploymentCoordinatorAgent",
    description="Orchestrates model deployment reviews across security, quality, resources, risk, and policy gateways.",
    edges=[
        (
            START,
            security_compliance_agent,
            model_quality_agent,
            infrastructure_readiness_agent,
            risk_assessment_agent,
            policy_decision_agent
        )
    ]
)
