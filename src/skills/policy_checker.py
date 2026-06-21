from typing import Any, Dict, List

def check_registry(image_uri: str, allowed_registries: List[str]) -> bool:
    """Verifies if the container image comes from an allowed registry."""
    return any(image_uri.startswith(reg) for reg in allowed_registries)

def evaluate_security_rules(vulnerabilities: List[Dict[str, Any]], max_severity: str) -> Dict[str, Any]:
    """Checks if the image vulnerabilities violate the maximum allowed severity."""
    severity_rank = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
    max_rank = severity_rank.get(max_severity.upper(), 0)
    
    violated = []
    for vul in vulnerabilities:
        vul_severity = vul.get("severity", "LOW").upper()
        if severity_rank.get(vul_severity, 0) > max_rank:
            violated.append(vul)
            
    return {
        "compliant": len(violated) == 0,
        "violations": violated
    }
