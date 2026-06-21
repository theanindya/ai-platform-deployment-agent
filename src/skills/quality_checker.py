from typing import Any, Dict

def check_model_quality(metrics: Dict[str, Any], policy: Dict[str, Any]) -> Dict[str, Any]:
    """Validates metrics against environment policies."""
    violations = []
    
    # Check F1 score
    f1_score = metrics.get("metrics", {}).get("f1_score", 0.0)
    min_f1 = policy.get("min_f1_score", 0.0)
    if f1_score < min_f1:
        violations.append(f"Model F1 score {f1_score} is below the minimum threshold of {min_f1}")
        
    # Check data drift
    drift = metrics.get("data_drift", 0.0)
    max_drift = policy.get("max_data_drift", 1.0)
    if drift > max_drift:
        violations.append(f"Model data drift {drift} exceeds the maximum threshold of {max_drift}")
        
    # Check bias
    bias_detected = metrics.get("bias_detected", False)
    if bias_detected:
        violations.append("Model evaluation reports bias detected in training data")
        
    return {
        "compliant": len(violations) == 0,
        "violations": violations
    }
