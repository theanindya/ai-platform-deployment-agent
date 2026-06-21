import re
from typing import Any, Dict

def parse_cpu(cpu_str: str) -> float:
    """Parses cpu string (e.g. '1.5', '500m') to float cores."""
    if not cpu_str:
        return 0.0
    cpu_str = str(cpu_str).strip()
    if cpu_str.endswith("m"):
        return float(cpu_str[:-1]) / 1000.0
    return float(cpu_str)

def parse_memory_to_gb(mem_str: str) -> float:
    """Parses memory string (e.g. '4Gi', '512Mi') to float GB."""
    if not mem_str:
        return 0.0
    mem_str = str(mem_str).strip()
    match = re.match(r"^(\d+)([a-zA-Z]*)$", mem_str)
    if not match:
        return 0.0
    value, unit = match.groups()
    val = float(value)
    unit = unit.lower()
    if unit in ("g", "gb", "gi"):
        return val
    if unit in ("m", "mb", "mi"):
        return val / 1024.0
    if unit in ("k", "kb", "ki"):
        return val / (1024.0 * 1024.0)
    return val / (1024.0 * 1024.0 * 1024.0) # Assume bytes

def check_resources(requested: Dict[str, str], cluster_status: Dict[str, Any]) -> Dict[str, Any]:
    """Validates cluster capacity for requested resources."""
    req_cpu = parse_cpu(requested.get("cpu_request", "0"))
    req_mem = parse_memory_to_gb(requested.get("memory_request", "0"))
    req_gpu = int(requested.get("gpu_request", "0"))
    
    cpu_avail = cluster_status["cpu"]["total_cores"] - cluster_status["cpu"]["allocated_cores"]
    mem_avail = cluster_status["memory"]["total_gb"] - cluster_status["memory"]["allocated_gb"]
    gpu_avail = cluster_status["gpu"]["total_cards"] - cluster_status["gpu"]["allocated_cards"]
    
    violations = []
    if req_cpu > cpu_avail:
        violations.append(f"Insufficient CPU: requested {req_cpu} cores, available {cpu_avail:.2f} cores")
    if req_mem > mem_avail:
        violations.append(f"Insufficient Memory: requested {req_mem} GB, available {mem_avail:.2f} GB")
    if req_gpu > gpu_avail:
        violations.append(f"Insufficient GPU: requested {req_gpu} cards, available {gpu_avail} cards")
        
    return {
        "compliant": len(violations) == 0,
        "violations": violations
    }
