import pytest
import json
import os
import uuid
from typing import Dict, Any

from google.adk.runners import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.genai import types

from src.mcp_server import MockMCPServer
from src.skills.policy_checker import check_registry, evaluate_security_rules
from src.skills.resource_validator import parse_cpu, parse_memory_to_gb, check_resources
from src.skills.quality_checker import check_model_quality
from src.agents.coordinator import DeploymentCoordinatorAgent
from src.models import (
    DeploymentRequest, SecurityFindings, QualityFindings,
    InfrastructureFindings, RiskAssessment, PolicyDecision,
    Verdict, RiskLevel, StateKeys,
)
from src.tools import MCP_TOOLS


# ---------------------------------------------------------------------------
# Helper: load deployment request JSON fixtures
# ---------------------------------------------------------------------------

def load_req(name: str) -> Dict[str, Any]:
    path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "data", "deployment_requests", f"{name}.json")
    )
    with open(path, "r") as f:
        return json.load(f)


async def run_workflow(req_data: Dict[str, Any]) -> tuple[Any, Any]:
    """Run the full ADK workflow and return (final_verdict_dict, session)."""
    session_service = InMemorySessionService()
    runner = Runner(
        node=DeploymentCoordinatorAgent,
        session_service=session_service,
        app_name="Test-Platform-Agent",
        auto_create_session=True
    )
    session_id = f"test-session-{uuid.uuid4()}"
    new_message = types.Content(
        role="user",
        parts=[types.Part(text=json.dumps(req_data))]
    )
    final_verdict = None
    async for event in runner.run_async(
        user_id="test-user",
        session_id=session_id,
        new_message=new_message
    ):
        if event.output is not None and isinstance(event.output, dict) and "verdict" in event.output:
            final_verdict = event.output

    session = await session_service.get_session(
        app_name="Test-Platform-Agent",
        user_id="test-user",
        session_id=session_id
    )
    return final_verdict, session


# ---------------------------------------------------------------------------
# Unit tests: MCP server
# ---------------------------------------------------------------------------

def test_mcp_server():
    """Verifies tool retrieval from the Mock MCP Server."""
    vulns = MockMCPServer.get_container_vulnerabilities("gcr.io/enterprise-platform/fraud-detection:v2")
    assert vulns["scan_status"] == "COMPLETED"
    assert len(vulns["vulnerabilities"]) == 0

    metrics = MockMCPServer.get_model_metrics("fraud-detection-v2")
    assert metrics["metrics"]["accuracy"] == 0.978

    cluster = MockMCPServer.get_cluster_status("k8s-cluster-dev")
    assert cluster["health_status"] == "HEALTHY"

    policy = MockMCPServer.get_policy_rules("prod")
    assert policy["min_f1_score"] == 0.90


# ---------------------------------------------------------------------------
# Unit tests: ADK FunctionTool wrappers
# ---------------------------------------------------------------------------

def test_mcp_function_tools_registered():
    """Verifies that all four MCP tools are registered as ADK FunctionTool instances."""
    expected = {
        "get_container_vulnerabilities",
        "get_model_metrics",
        "get_cluster_status",
        "get_policy_rules",
    }
    assert expected == set(MCP_TOOLS.keys()), (
        f"Expected tools {expected}, got {set(MCP_TOOLS.keys())}"
    )

def test_mcp_function_tools_callable():
    """Verifies each FunctionTool's underlying function returns expected data."""
    vuln_tool = MCP_TOOLS["get_container_vulnerabilities"]
    result = vuln_tool.func(image_uri="gcr.io/enterprise-platform/fraud-detection:v2")
    assert result["scan_status"] == "COMPLETED"

    metrics_tool = MCP_TOOLS["get_model_metrics"]
    result = metrics_tool.func(model_id="fraud-detection-v2")
    assert result["metrics"]["f1_score"] == 0.961

    cluster_tool = MCP_TOOLS["get_cluster_status"]
    result = cluster_tool.func(cluster_name="k8s-cluster-prod-1")
    assert result["health_status"] == "HEALTHY"

    policy_tool = MCP_TOOLS["get_policy_rules"]
    result = policy_tool.func(environment="prod")
    assert "min_f1_score" in result


# ---------------------------------------------------------------------------
# Unit tests: Pydantic schemas
# ---------------------------------------------------------------------------

def test_pydantic_schemas_validation():
    """Verifies that all Pydantic schemas validate correctly from dict input."""
    req = DeploymentRequest.model_validate({
        "request_id": "test-001",
        "model_name": "fraud-detection-v2",
        "model_version": "2.0.0",
        "container_image": "gcr.io/enterprise-platform/fraud-detection:v2",
        "target_cluster": "k8s-cluster-prod-1",
        "environment": "prod",
        "monitoring_enabled": True,
        "rollback_strategy": "rolling-update",
    })
    assert req.environment.value == "prod"
    assert req.rollback_strategy.value == "rolling-update"

    risk = RiskAssessment(risk_score=45, risk_level=RiskLevel.MEDIUM)
    decision = PolicyDecision(
        verdict=Verdict.APPROVED_WITH_WARNINGS,
        reason="Test reason",
        violations=["[Security] test violation"],
        risk_assessment=risk,
    )
    assert decision.verdict == Verdict.APPROVED_WITH_WARNINGS
    dumped = decision.model_dump(mode="json")
    assert dumped["verdict"] == "APPROVED WITH WARNINGS"


def test_state_keys_constants():
    """Verifies StateKeys provides all expected constants."""
    assert StateKeys.REQUEST == "request"
    assert StateKeys.SECURITY_FINDINGS == "security_findings"
    assert StateKeys.QUALITY_FINDINGS == "quality_findings"
    assert StateKeys.INFRA_FINDINGS == "infra_findings"
    assert StateKeys.RISK_ASSESSMENT == "risk_assessment"
    assert StateKeys.FINAL_VERDICT == "final_verdict"


# ---------------------------------------------------------------------------
# Unit tests: skills helpers
# ---------------------------------------------------------------------------

def test_skills():
    """Validates the skill check helper functions."""
    assert check_registry("gcr.io/enterprise-platform/model:v1", ["gcr.io/enterprise-platform/"]) is True
    assert check_registry("docker.io/untrusted/model:v1", ["gcr.io/enterprise-platform/"]) is False

    assert parse_cpu("500m") == 0.5
    assert parse_cpu("1.5") == 1.5
    assert parse_memory_to_gb("4Gi") == 4.0
    assert parse_memory_to_gb("512Mi") == 0.5


# ---------------------------------------------------------------------------
# Integration tests: full ADK multi-agent workflow
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_full_workflow_standard_req():
    """Tests the full multi-agent workflow on a standard compliant request."""
    req_data = load_req("req_001_standard")
    final_verdict, session = await run_workflow(req_data)

    assert final_verdict is not None
    assert final_verdict["verdict"] == "APPROVED"
    assert len(final_verdict["violations"]) == 0
    assert final_verdict["risk_assessment"]["risk_level"] == "LOW"

    # Verify tool call log was populated
    tool_calls = session.state.get("tool_calls", [])
    assert len(tool_calls) >= 4  # at least 4 MCP tool calls

    # Verify PolicyDecision fallback mode (no API key in CI)
    assert session.state.get("policy_llm_used") in (True, False)


@pytest.mark.asyncio
async def test_full_workflow_critical_cve():
    """Tests the workflow on a request with critical container vulnerabilities."""
    req_data = load_req("req_002_critical_cve")
    final_verdict, session = await run_workflow(req_data)

    assert final_verdict is not None
    assert final_verdict["verdict"] == "BLOCKED"
    assert any("cve" in str(v).lower() for v in final_verdict["violations"])

    # Verify Pydantic schema round-trip
    decision = PolicyDecision.model_validate({
        **final_verdict,
        "risk_assessment": final_verdict["risk_assessment"]
    })
    assert decision.verdict == Verdict.BLOCKED


@pytest.mark.asyncio
async def test_full_workflow_poor_metrics():
    """Tests the workflow on a request with poor model quality metrics."""
    req_data = load_req("req_003_poor_metrics")
    final_verdict, session = await run_workflow(req_data)

    assert final_verdict is not None
    assert final_verdict["verdict"] in ("APPROVED WITH WARNINGS", "BLOCKED")

    # Verify quality findings were stored correctly in session state
    quality = QualityFindings.model_validate(session.state.get(StateKeys.QUALITY_FINDINGS, {}))
    assert quality.data_drift > 0.1 or not quality.compliant
