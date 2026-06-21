import json
import os
from typing import Any, Dict

# Paths to synthetic database files
DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))
MODEL_REGISTRY_PATH = os.path.join(DATA_DIR, "model_registry.json")
SECURITY_SCANS_PATH = os.path.join(DATA_DIR, "security_scans.json")
CLUSTER_STATUS_PATH = os.path.join(DATA_DIR, "cluster_status.json")
ENTERPRISE_POLICIES_PATH = os.path.join(DATA_DIR, "enterprise_policies.json")

def load_json(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {}
    with open(path, "r") as f:
        return json.load(f)

class MockMCPServer:
    """Mock MCP server mimicking Model Context Protocol tools for hybrid cloud AI deployment."""

    @staticmethod
    def get_container_vulnerabilities(image_uri: str) -> Dict[str, Any]:
        """Queries the mock container registry scan tool.

        Args:
            image_uri: The container image URI (e.g. gcr.io/enterprise-platform/fraud-detection:v2).

        Returns:
            A dict containing the scan status and list of vulnerabilities.
        """
        data = load_json(SECURITY_SCANS_PATH)
        images = data.get("images", {})
        if image_uri in images:
            return images[image_uri]
        # Return a fallback for images not in the synthetic registry - treat as unscanned with a warning
        return {
            "image_uri": image_uri,
            "scan_status": "UNSCANNED",
            "vulnerabilities": [
                {
                    "cve_id": "WARN-UNSCANNED",
                    "severity": "LOW",
                    "package": "unknown",
                    "description": "Image has not been scanned in the enterprise registry. Recommend running a scan before production deployment.",
                    "fixed_version": "n/a"
                }
            ]
        }

    @staticmethod
    def get_model_metrics(model_id: str) -> Dict[str, Any]:
        """Queries the mock model registry evaluation tool.

        Args:
            model_id: The ID of the model (e.g. fraud-detection-v2).

        Returns:
            A dict containing accuracy, f1_score, latency, drift, and bias flags.
        """
        data = load_json(MODEL_REGISTRY_PATH)
        models = data.get("models", {})
        if model_id in models:
            return models[model_id]
        return {
            "model_id": model_id,
            "metrics": {"accuracy": 0.0, "f1_score": 0.0, "latency_p95_ms": 999.9},
            "data_drift": 1.0,
            "bias_detected": True
        }

    @staticmethod
    def get_cluster_status(cluster_name: str) -> Dict[str, Any]:
        """Queries the target cluster status and resource capacities.

        Args:
            cluster_name: Name of the Kubernetes cluster (e.g. k8s-cluster-prod-1).

        Returns:
            A dict containing allocated and total cores, memory, gpu, monitoring and rollback support status.
        """
        data = load_json(CLUSTER_STATUS_PATH)
        clusters = data.get("clusters", {})
        if cluster_name in clusters:
            return clusters[cluster_name]
        return {
            "cluster_name": cluster_name,
            "health_status": "UNREACHABLE",
            "cpu": {"total_cores": 0.0, "allocated_cores": 0.0},
            "memory": {"total_gb": 0.0, "allocated_gb": 0.0},
            "gpu": {"total_cards": 0, "allocated_cards": 0},
            "monitoring_installed": False,
            "rollback_supported": False
        }

    @staticmethod
    def get_policy_rules(environment: str) -> Dict[str, Any]:
        """Retrieves policy rules / thresholds for the target environment.

        Args:
            environment: The deployment environment ('dev', 'test', 'prod').

        Returns:
            A dict of minimum requirements and allowlists.
        """
        data = load_json(ENTERPRISE_POLICIES_PATH)
        policies = data.get("policies", {})
        if environment in policies:
            return policies[environment]
        # Strict fallback policy
        return {
            "min_f1_score": 0.95,
            "max_allowed_cve_severity": "LOW",
            "allowed_registries": ["gcr.io/enterprise-platform/"],
            "require_monitoring": True,
            "require_rollback": True,
            "max_data_drift": 0.01
        }
