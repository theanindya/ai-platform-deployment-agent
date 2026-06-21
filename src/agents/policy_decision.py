"""
PolicyDecisionAgent — Hybrid LLM + Rule-based final verdict node.

Execution strategy:
  1. If GOOGLE_API_KEY is set in the environment, dynamically invoke a
     Gemini-backed LlmAgent via ctx.run_node(). The LLM receives a structured
     JSON prompt containing all upstream findings and must return a valid JSON
     PolicyDecision object.
  2. If no API key is available (or if the LLM call fails), fall back to the
     deterministic rule-based logic that was the original implementation.
     This ensures tests always pass locally without credentials.

Final output is always a PolicyDecision validated via the Pydantic schema.
"""
import json
import logging
import os
from typing import Any, Dict

from google.adk.agents import LlmAgent, Context
from google.adk.workflow import node
from google.genai.types import GenerateContentConfig

from src.models import (
    DeploymentRequest,
    SecurityFindings,
    QualityFindings,
    InfrastructureFindings,
    RiskAssessment,
    PolicyDecision,
    Verdict,
    StateKeys,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompt for the Gemini-backed LlmAgent
# ---------------------------------------------------------------------------

POLICY_AGENT_INSTRUCTION = """
You are an enterprise AI deployment policy officer for a hybrid cloud platform team.

Your role is to review AI model deployment requests and produce a final policy decision
based on findings from four specialist agents: SecurityComplianceAgent,
ModelQualityAgent, InfrastructureReadinessAgent, and RiskAssessmentAgent.

You will receive a JSON object containing:
  - request: the deployment request details
  - security_findings: CVE violations and registry compliance
  - quality_findings: model accuracy, drift, bias, and quality violations
  - infra_findings: cluster health, resource capacity, and infrastructure violations
  - risk_assessment: composite risk score (0-100) and risk level (LOW/MEDIUM/HIGH)

Based on these findings, apply the following policy rules:
  1. If risk_level is HIGH → verdict MUST be BLOCKED
  2. If environment is prod AND any violations exist → verdict MUST be BLOCKED
  3. If any finding mentions "critical" or "high severity" → verdict SHOULD be BLOCKED
  4. If violations exist or risk_level is MEDIUM → verdict SHOULD be APPROVED WITH WARNINGS
  5. If all checks pass with LOW risk → verdict SHOULD be APPROVED

You must respond with ONLY a valid JSON object — no markdown, no explanation outside JSON.
The JSON must have exactly these fields:
{
  "verdict": "APPROVED" | "APPROVED WITH WARNINGS" | "BLOCKED",
  "reason": "<concise 1-2 sentence explanation referencing specific findings>",
  "recommended_actions": ["<action 1>", "<action 2>", ...]
}
""".strip()


# ---------------------------------------------------------------------------
# Gemini LlmAgent (instantiated once if API key is available)
# ---------------------------------------------------------------------------

def _build_llm_agent() -> LlmAgent | None:
    """Build the Gemini LlmAgent if API credentials are available."""
    api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GOOGLE_GENAI_API_KEY")
    if not api_key:
        return None
    try:
        return LlmAgent(
            name="GeminiPolicyReviewer",
            model="gemini-2.0-flash",
            instruction=POLICY_AGENT_INSTRUCTION,
            description="Gemini-backed LLM agent for final deployment policy reasoning.",
            rerun_on_resume=True,
            generate_content_config=GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1,  # low temperature for consistent structured output
            ),
        )
    except Exception as e:
        logger.warning("Failed to build Gemini LlmAgent: %s. Falling back to rules.", e)
        return None


_GEMINI_POLICY_AGENT = _build_llm_agent()


# ---------------------------------------------------------------------------
# Helper: deterministic rule-based fallback
# ---------------------------------------------------------------------------

def _rule_based_verdict(
    request: DeploymentRequest,
    security: SecurityFindings,
    quality: QualityFindings,
    infra: InfrastructureFindings,
    risk: RiskAssessment,
    all_violations: list[str],
) -> tuple[Verdict, str]:
    """Apply deterministic policy rules and return (verdict, reason)."""
    if risk.risk_level.value == "HIGH":
        return (
            Verdict.BLOCKED,
            f"Blocked: High overall risk score ({risk.risk_score}/100). "
            "Resolve all critical findings before proceeding.",
        )
    if request.environment.value == "prod" and len(all_violations) > 0:
        return (
            Verdict.BLOCKED,
            f"Blocked: Production deployments require zero policy violations. "
            f"{len(all_violations)} violation(s) found.",
        )
    if any(
        kw in str(v).lower()
        for v in all_violations
        for kw in ("critical", "high severity")
    ):
        return (
            Verdict.BLOCKED,
            "Blocked: Critical or high-severity security issues detected.",
        )
    if len(all_violations) > 0 or risk.risk_level.value == "MEDIUM":
        return (
            Verdict.APPROVED_WITH_WARNINGS,
            "Approved with warnings: Minor policy non-compliance or medium risk level detected. "
            "Review the violations before promotion to production.",
        )
    return (
        Verdict.APPROVED,
        "Approved: All security, quality, and infrastructure checks passed.",
    )


# ---------------------------------------------------------------------------
# PolicyDecisionAgent @node
# ---------------------------------------------------------------------------

@node(name="PolicyDecisionAgent", rerun_on_resume=True)
async def policy_decision_agent(ctx: Context, node_input: Any) -> Dict[str, Any]:
    """Applies enterprise gateway policy rules to yield a final verdict.

    If GOOGLE_API_KEY is set, delegates final reasoning to a Gemini LlmAgent
    via ctx.run_node(). Falls back to deterministic rules if no API key is
    available or if the LLM call fails.

    Reads:  ctx.state[StateKeys.REQUEST]           -> DeploymentRequest
            ctx.state[StateKeys.SECURITY_FINDINGS] -> SecurityFindings
            ctx.state[StateKeys.QUALITY_FINDINGS]  -> QualityFindings
            ctx.state[StateKeys.INFRA_FINDINGS]    -> InfrastructureFindings
            ctx.state[StateKeys.RISK_ASSESSMENT]   -> RiskAssessment
    Writes: ctx.state[StateKeys.FINAL_VERDICT]     -> PolicyDecision
    """
    # Read and validate all upstream schemas
    request  = DeploymentRequest.model_validate(ctx.state.get(StateKeys.REQUEST, {}))
    security = SecurityFindings.model_validate(ctx.state.get(StateKeys.SECURITY_FINDINGS, {}))
    quality  = QualityFindings.model_validate(ctx.state.get(StateKeys.QUALITY_FINDINGS, {}))
    infra    = InfrastructureFindings.model_validate(ctx.state.get(StateKeys.INFRA_FINDINGS, {}))
    risk     = RiskAssessment.model_validate(ctx.state.get(StateKeys.RISK_ASSESSMENT, {}))

    # Collect all violations across domains
    all_violations: list[str] = []
    all_violations.extend([f"[Security] {v}" for v in security.violations])
    all_violations.extend([f"[Quality] {v}" for v in quality.violations])
    all_violations.extend([f"[Infrastructure] {v}" for v in infra.violations])

    recommended_actions: list[str] = []
    llm_used = False

    # ------------------------------------------------------------------
    # Path A: LLM reasoning via Gemini
    # ------------------------------------------------------------------
    if _GEMINI_POLICY_AGENT is not None:
        try:
            prompt_payload = json.dumps({
                "request": request.model_dump(mode="json"),
                "security_findings": security.model_dump(mode="json"),
                "quality_findings": quality.model_dump(mode="json"),
                "infra_findings": infra.model_dump(mode="json"),
                "risk_assessment": risk.model_dump(mode="json"),
                "all_violations": all_violations,
            }, indent=2)

            llm_output = await ctx.run_node(
                _GEMINI_POLICY_AGENT,
                node_input=prompt_payload,
            )

            # Parse and validate the LLM JSON response
            raw = llm_output if isinstance(llm_output, dict) else json.loads(str(llm_output))

            raw_verdict = raw.get("verdict", "BLOCKED").strip().upper()
            # Normalise variant spellings
            if "WARNING" in raw_verdict:
                raw_verdict = "APPROVED WITH WARNINGS"

            verdict = Verdict(raw_verdict)
            reason = raw.get("reason", "No reason provided by LLM.")
            recommended_actions = raw.get("recommended_actions", [])
            llm_used = True
            logger.info("PolicyDecisionAgent: Gemini verdict = %s", verdict)

        except Exception as e:
            logger.warning(
                "PolicyDecisionAgent: LLM call failed (%s). Falling back to rules.", e
            )
            verdict, reason = _rule_based_verdict(
                request, security, quality, infra, risk, all_violations
            )
    else:
        # ------------------------------------------------------------------
        # Path B: Deterministic rule-based fallback
        # ------------------------------------------------------------------
        verdict, reason = _rule_based_verdict(
            request, security, quality, infra, risk, all_violations
        )

    # Build and validate the final decision
    decision = PolicyDecision(
        verdict=verdict,
        reason=reason,
        violations=all_violations,
        risk_assessment=risk,
    )

    ctx.state[StateKeys.FINAL_VERDICT] = decision.model_dump(mode="json")
    ctx.state["policy_llm_used"] = llm_used
    ctx.state["policy_recommended_actions"] = recommended_actions
    return decision.model_dump(mode="json")
