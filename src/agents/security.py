from typing import Any, Dict
from google.adk.workflow import node
from google.adk.agents import Context
from src.skills.policy_checker import check_registry, evaluate_security_rules
from src.utils.helpers import parse_input_to_dict
from src.models import DeploymentRequest, SecurityFindings, StateKeys
from src.tools import (
    get_container_vulnerabilities_tool,
    get_policy_rules_tool,
)


@node(name="SecurityComplianceAgent", rerun_on_resume=True)
def security_compliance_agent(ctx: Context, node_input: Any) -> Dict[str, Any]:
    """Evaluates container security scans and registry policies.

    ADK Tools used:
        - get_container_vulnerabilities: CVE scan results from the container registry
        - get_policy_rules: Enterprise security policy thresholds

    Reads:  node_input (raw ADK Content carrying the deployment JSON)
    Writes: ctx.state[StateKeys.REQUEST]           -> DeploymentRequest (dict)
            ctx.state[StateKeys.SECURITY_FINDINGS] -> SecurityFindings (dict)
            ctx.state["tool_calls"]                -> list of tool invocation records
    """
    # Parse and validate the incoming deployment request
    raw = parse_input_to_dict(node_input)
    request = DeploymentRequest.model_validate(raw)

    # Persist the validated request so all downstream agents share it
    ctx.state[StateKeys.REQUEST] = request.model_dump(mode="json")

    # Initialise shared tool call log
    ctx.state.setdefault("tool_calls", [])

    # --- ADK Tool call 1: get_container_vulnerabilities ---
    vulnerabilities_data = get_container_vulnerabilities_tool.func(
        image_uri=request.container_image
    )
    ctx.state["tool_calls"].append({
        "tool": get_container_vulnerabilities_tool.name,
        "agent": "SecurityComplianceAgent",
        "args": {"image_uri": request.container_image},
        "result_summary": {
            "scan_status": vulnerabilities_data.get("scan_status"),
            "vuln_count": len(vulnerabilities_data.get("vulnerabilities", [])),
        },
    })

    # --- ADK Tool call 2: get_policy_rules ---
    policy_data = get_policy_rules_tool.func(
        environment=request.environment.value
    )
    ctx.state["tool_calls"].append({
        "tool": get_policy_rules_tool.name,
        "agent": "SecurityComplianceAgent",
        "args": {"environment": request.environment.value},
        "result_summary": {
            "max_allowed_cve_severity": policy_data.get("max_allowed_cve_severity"),
            "allowed_registries": policy_data.get("allowed_registries"),
        },
    })

    # Evaluate policy compliance
    allowed_registries = policy_data.get("allowed_registries", [])
    registry_ok = check_registry(request.container_image, allowed_registries)

    max_severity = policy_data.get("max_allowed_cve_severity", "HIGH")
    security_eval = evaluate_security_rules(
        vulnerabilities_data.get("vulnerabilities", []),
        max_severity
    )

    violations = [
        f"{v.get('cve_id', 'UNKNOWN')} ({v.get('severity', 'UNKNOWN')}) in package "
        f"'{v.get('package', 'unknown')}' — exceeds max allowed severity '{max_severity}'"
        for v in security_eval.get("violations", [])
    ]
    if not registry_ok:
        violations.append(
            f"Image registry is not in the allowed list: {allowed_registries}"
        )

    findings = SecurityFindings(
        compliant=security_eval.get("compliant", False) and registry_ok,
        violations=violations,
        vulnerabilities=vulnerabilities_data.get("vulnerabilities", []),
    )

    ctx.state[StateKeys.SECURITY_FINDINGS] = findings.model_dump(mode="json")
    return findings.model_dump(mode="json")
