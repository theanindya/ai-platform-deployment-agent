from typing import Any, Dict
from google.adk.workflow import node
from google.adk.agents import Context
from src.models import (
    SecurityFindings,
    QualityFindings,
    InfrastructureFindings,
    RiskAssessment,
    RiskLevel,
    StateKeys,
)


@node(name="RiskAssessmentAgent", rerun_on_resume=True)
def risk_assessment_agent(ctx: Context, node_input: Any) -> Dict[str, Any]:
    """Evaluates combined findings to produce a composite risk score and level.

    Reads:  ctx.state[StateKeys.SECURITY_FINDINGS] -> SecurityFindings (dict)
            ctx.state[StateKeys.QUALITY_FINDINGS]  -> QualityFindings (dict)
            ctx.state[StateKeys.INFRA_FINDINGS]    -> InfrastructureFindings (dict)
    Writes: ctx.state[StateKeys.RISK_ASSESSMENT]   -> RiskAssessment (dict)
    """
    # Read and validate upstream findings using schemas
    security = SecurityFindings.model_validate(
        ctx.state.get(StateKeys.SECURITY_FINDINGS, {})
    )
    quality = QualityFindings.model_validate(
        ctx.state.get(StateKeys.QUALITY_FINDINGS, {})
    )
    infra = InfrastructureFindings.model_validate(
        ctx.state.get(StateKeys.INFRA_FINDINGS, {})
    )

    score = 0

    # 1. Security risk scoring — weighted by CVE severity
    for v in security.vulnerabilities:
        severity = str(v.get("severity", "LOW")).upper()
        if severity == "CRITICAL":
            score += 40
        elif severity == "HIGH":
            score += 25
        elif severity == "MEDIUM":
            score += 10
        else:
            score += 2

    if not security.compliant:
        score += 20

    # 2. Quality risk scoring
    if not quality.compliant:
        score += 25
    if quality.bias_detected:
        score += 20
    if quality.data_drift > 0.1:
        score += 15

    # 3. Infrastructure risk scoring
    if not infra.compliant:
        score += 25
    if infra.cluster_health != "HEALTHY":
        score += 30

    # Cap at 100
    score = min(score, 100)

    # Determine risk level
    if score >= 65:
        level = RiskLevel.HIGH
    elif score >= 25:
        level = RiskLevel.MEDIUM
    else:
        level = RiskLevel.LOW

    # Build and validate findings using schema
    assessment = RiskAssessment(risk_score=score, risk_level=level)

    ctx.state[StateKeys.RISK_ASSESSMENT] = assessment.model_dump(mode="json")
    return assessment.model_dump(mode="json")
