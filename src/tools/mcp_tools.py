"""
ADK FunctionTool wrappers for the Mock MCP Server.

Each function here is a standalone, fully typed and documented callable that is
wrapped as a google.adk.tools.FunctionTool instance. This gives each MCP operation
a formal ADK tool identity — including a registered name, parameter schema, and
description — which is used in the tool call log and would enable LLM-driven
invocation in a future LlmAgent upgrade.

In the current @node-based workflow, agents call tool.func(...) directly and log
every invocation to ctx.state["tool_calls"] for full traceability.
"""
from typing import Any, Dict, List
from google.adk.tools import FunctionTool
from src.mcp_server import MockMCPServer


# ---------------------------------------------------------------------------
# Tool functions — standalone callables with full type hints and docstrings
# ---------------------------------------------------------------------------

def get_container_vulnerabilities(image_uri: str) -> Dict[str, Any]:
    """Query the enterprise container registry for CVE scan results.

    Retrieves the security scan status and list of known vulnerabilities
    (CVEs) for a given container image URI. Returns UNSCANNED status with
    a LOW-severity warning for images not yet registered in the enterprise
    registry.

    Args:
        image_uri: Full container image URI, e.g.
            'gcr.io/enterprise-platform/fraud-detection:v2'.

    Returns:
        A dict with keys:
            - image_uri (str): The image that was scanned.
            - scan_status (str): 'COMPLETED', 'FAILED', or 'UNSCANNED'.
            - vulnerabilities (list): List of CVE records, each with
              cve_id, severity, package, and fixed_version fields.
    """
    return MockMCPServer.get_container_vulnerabilities(image_uri)


def get_model_metrics(model_id: str) -> Dict[str, Any]:
    """Retrieve quality metrics for a registered AI model from the model registry.

    Returns performance metrics including accuracy, F1 score, and p95 latency,
    as well as data drift and bias flags. Falls back to zero metrics with
    worst-case drift/bias flags for models not found in the registry.

    Args:
        model_id: The model identifier as registered in the model registry,
            e.g. 'fraud-detection-v2'.

    Returns:
        A dict with keys:
            - model_id (str): The queried model ID.
            - metrics (dict): accuracy, f1_score, latency_p95_ms.
            - data_drift (float): Measured drift score (0.0–1.0).
            - bias_detected (bool): Whether bias was detected.
    """
    return MockMCPServer.get_model_metrics(model_id)


def get_cluster_status(cluster_name: str) -> Dict[str, Any]:
    """Query the health and resource capacity of a GKE-style Kubernetes cluster.

    Returns the cluster's current health status, CPU/memory/GPU allocation
    percentages, and whether monitoring and rollback capabilities are installed.
    Falls back to UNREACHABLE status for unknown clusters.

    Args:
        cluster_name: Name of the target cluster, e.g. 'k8s-cluster-prod-1'.

    Returns:
        A dict with keys:
            - cluster_name (str): The queried cluster.
            - health_status (str): 'HEALTHY', 'DEGRADED', or 'UNREACHABLE'.
            - cpu (dict): total_cores, allocated_cores.
            - memory (dict): total_gb, allocated_gb.
            - gpu (dict): total_cards, allocated_cards.
            - monitoring_installed (bool)
            - rollback_supported (bool)
    """
    return MockMCPServer.get_cluster_status(cluster_name)


def get_policy_rules(environment: str) -> Dict[str, Any]:
    """Retrieve enterprise deployment policy rules for a target environment.

    Returns the minimum quality thresholds, allowed container registries,
    maximum CVE severity levels, and monitoring/rollback requirements for the
    given environment tier. Falls back to strict production-grade policy for
    unknown environments.

    Args:
        environment: Target environment tier — 'dev', 'test', or 'prod'.

    Returns:
        A dict with keys:
            - min_f1_score (float): Minimum acceptable F1 score.
            - max_allowed_cve_severity (str): 'LOW', 'MEDIUM', 'HIGH', or 'CRITICAL'.
            - allowed_registries (list[str]): Allowed container registry prefixes.
            - require_monitoring (bool): Whether monitoring must be enabled.
            - require_rollback (bool): Whether a rollback strategy is required.
            - max_data_drift (float): Maximum acceptable data drift score.
    """
    return MockMCPServer.get_policy_rules(environment)


# ---------------------------------------------------------------------------
# ADK FunctionTool instances — registered ADK tool objects
# ---------------------------------------------------------------------------

get_container_vulnerabilities_tool = FunctionTool(func=get_container_vulnerabilities)
get_model_metrics_tool             = FunctionTool(func=get_model_metrics)
get_cluster_status_tool            = FunctionTool(func=get_cluster_status)
get_policy_rules_tool              = FunctionTool(func=get_policy_rules)

# Convenience registry for introspection / documentation
MCP_TOOLS = {
    get_container_vulnerabilities_tool.name: get_container_vulnerabilities_tool,
    get_model_metrics_tool.name:             get_model_metrics_tool,
    get_cluster_status_tool.name:            get_cluster_status_tool,
    get_policy_rules_tool.name:              get_policy_rules_tool,
}
