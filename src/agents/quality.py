from typing import Any, Dict
from google.adk.workflow import node
from google.adk.agents import Context
from src.skills.quality_checker import check_model_quality
from src.models import DeploymentRequest, QualityFindings, ModelMetrics, StateKeys
from src.tools import get_model_metrics_tool, get_policy_rules_tool


@node(name="ModelQualityAgent", rerun_on_resume=True)
def model_quality_agent(ctx: Context, node_input: Any) -> Dict[str, Any]:
    """Validates model accuracy, latency, data drift, and bias.

    ADK Tools used:
        - get_model_metrics: Performance metrics from the model registry
        - get_policy_rules: Quality thresholds per environment

    Reads:  ctx.state[StateKeys.REQUEST]          -> DeploymentRequest (dict)
    Writes: ctx.state[StateKeys.QUALITY_FINDINGS] -> QualityFindings (dict)
            ctx.state["tool_calls"]               -> appends tool invocation records
    """
    request = DeploymentRequest.model_validate(ctx.state.get(StateKeys.REQUEST, {}))

    # --- ADK Tool call: get_model_metrics ---
    metrics_data = get_model_metrics_tool.func(model_id=request.model_name)
    ctx.state["tool_calls"].append({
        "tool": get_model_metrics_tool.name,
        "agent": "ModelQualityAgent",
        "args": {"model_id": request.model_name},
        "result_summary": {
            "accuracy": metrics_data.get("metrics", {}).get("accuracy"),
            "f1_score": metrics_data.get("metrics", {}).get("f1_score"),
            "data_drift": metrics_data.get("data_drift"),
            "bias_detected": metrics_data.get("bias_detected"),
        },
    })

    # --- ADK Tool call: get_policy_rules ---
    policy_data = get_policy_rules_tool.func(environment=request.environment.value)
    ctx.state["tool_calls"].append({
        "tool": get_policy_rules_tool.name,
        "agent": "ModelQualityAgent",
        "args": {"environment": request.environment.value},
        "result_summary": {
            "min_f1_score": policy_data.get("min_f1_score"),
            "max_data_drift": policy_data.get("max_data_drift"),
        },
    })

    quality_eval = check_model_quality(metrics_data, policy_data)

    raw_metrics = metrics_data.get("metrics", {})
    findings = QualityFindings(
        compliant=quality_eval.get("compliant", False),
        violations=quality_eval.get("violations", []),
        metrics=ModelMetrics(
            accuracy=raw_metrics.get("accuracy", 0.0),
            f1_score=raw_metrics.get("f1_score", 0.0),
            latency_p95_ms=raw_metrics.get("latency_p95_ms", 0.0),
        ),
        data_drift=metrics_data.get("data_drift", 0.0),
        bias_detected=metrics_data.get("bias_detected", False),
    )

    ctx.state[StateKeys.QUALITY_FINDINGS] = findings.model_dump(mode="json")
    return findings.model_dump(mode="json")
