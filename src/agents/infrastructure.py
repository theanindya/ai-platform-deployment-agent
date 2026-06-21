from typing import Any, Dict
from google.adk.workflow import node
from google.adk.agents import Context
from src.skills.resource_validator import check_resources
from src.models import DeploymentRequest, InfrastructureFindings, StateKeys
from src.tools import get_cluster_status_tool, get_policy_rules_tool


@node(name="InfrastructureReadinessAgent", rerun_on_resume=True)
def infrastructure_readiness_agent(ctx: Context, node_input: Any) -> Dict[str, Any]:
    """Checks GKE-style cluster status, capacities, monitoring, and rollback capabilities.

    ADK Tools used:
        - get_cluster_status: Cluster health and resource capacity
        - get_policy_rules: Infrastructure requirements per environment

    Reads:  ctx.state[StateKeys.REQUEST]        -> DeploymentRequest (dict)
    Writes: ctx.state[StateKeys.INFRA_FINDINGS] -> InfrastructureFindings (dict)
            ctx.state["tool_calls"]             -> appends tool invocation records
    """
    request = DeploymentRequest.model_validate(ctx.state.get(StateKeys.REQUEST, {}))

    # --- ADK Tool call: get_cluster_status ---
    cluster_status = get_cluster_status_tool.func(cluster_name=request.target_cluster)
    ctx.state["tool_calls"].append({
        "tool": get_cluster_status_tool.name,
        "agent": "InfrastructureReadinessAgent",
        "args": {"cluster_name": request.target_cluster},
        "result_summary": {
            "health_status": cluster_status.get("health_status"),
            "monitoring_installed": cluster_status.get("monitoring_installed"),
            "rollback_supported": cluster_status.get("rollback_supported"),
        },
    })

    # --- ADK Tool call: get_policy_rules ---
    policy_data = get_policy_rules_tool.func(environment=request.environment.value)
    ctx.state["tool_calls"].append({
        "tool": get_policy_rules_tool.name,
        "agent": "InfrastructureReadinessAgent",
        "args": {"environment": request.environment.value},
        "result_summary": {
            "require_monitoring": policy_data.get("require_monitoring"),
            "require_rollback": policy_data.get("require_rollback"),
        },
    })

    resource_eval = check_resources(request.model_dump(mode="json"), cluster_status)
    violations = list(resource_eval.get("violations", []))

    if policy_data.get("require_monitoring", False) and not request.monitoring_enabled:
        violations.append(
            "Monitoring is required for this environment but was disabled in the request"
        )
    if policy_data.get("require_rollback", False) and request.rollback_strategy.value == "none":
        violations.append(
            "Rollback strategy is required for this environment but was set to 'none'"
        )
    if cluster_status.get("health_status") != "HEALTHY":
        violations.append(
            f"Target cluster health is: {cluster_status.get('health_status')}"
        )

    cpu_total = cluster_status.get("cpu", {}).get("total_cores", 0)
    cpu_allocated = cluster_status.get("cpu", {}).get("allocated_cores", 0)
    cpu_pct = (cpu_allocated / cpu_total * 100) if cpu_total > 0 else 0.0

    findings = InfrastructureFindings(
        compliant=len(violations) == 0,
        violations=violations,
        cluster_health=cluster_status.get("health_status", "UNKNOWN"),
        cpu_allocation_percent=cpu_pct,
    )

    ctx.state[StateKeys.INFRA_FINDINGS] = findings.model_dump(mode="json")
    return findings.model_dump(mode="json")
