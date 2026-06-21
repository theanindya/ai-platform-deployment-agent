"""
Pydantic schemas for all data flowing through the ADK multi-agent workflow.

Each schema represents the data contract for one stage of the pipeline.
Agents write typed model instances (serialised via .model_dump()) to ctx.state
and read them back via model_validate() — ensuring all inter-agent communication
is schema-validated and self-documenting.
"""
from __future__ import annotations
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class Environment(str, Enum):
    dev = "dev"
    test = "test"
    prod = "prod"


class RollbackStrategy(str, Enum):
    none = "none"
    rolling_update = "rolling-update"


class CveSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class Verdict(str, Enum):
    APPROVED = "APPROVED"
    APPROVED_WITH_WARNINGS = "APPROVED WITH WARNINGS"
    BLOCKED = "BLOCKED"


# ---------------------------------------------------------------------------
# DeploymentRequest — mirrors the FastAPI request body
# ---------------------------------------------------------------------------

class DeploymentRequest(BaseModel):
    request_id: str = Field(..., description="Unique ID for the deployment request")
    model_name: str = Field(..., description="ID or name of the AI model to deploy")
    model_version: str = Field(..., description="Version string of the AI model")
    container_image: str = Field(..., description="Full container image URI")
    target_cluster: str = Field(..., description="Target cluster name")
    environment: Environment = Field(..., description="Target environment (dev, test, prod)")
    namespace: str = Field(default="default", description="Kubernetes namespace")
    cpu_request: str = Field(default="100m", description="CPU request (e.g. 500m, 1.0)")
    memory_request: str = Field(default="256Mi", description="Memory request (e.g. 512Mi, 2Gi)")
    gpu_request: str = Field(default="0", description="Number of GPUs requested")
    monitoring_enabled: bool = Field(default=False, description="Whether monitoring should be enabled")
    rollback_strategy: RollbackStrategy = Field(
        default=RollbackStrategy.none,
        description="Rollback strategy (none, rolling-update)"
    )


# ---------------------------------------------------------------------------
# Vulnerability — individual CVE entry from the MCP scan tool
# ---------------------------------------------------------------------------

class Vulnerability(BaseModel):
    cve_id: str
    severity: CveSeverity
    package: str
    description: Optional[str] = None
    fixed_version: Optional[str] = None


# ---------------------------------------------------------------------------
# SecurityFindings — output of SecurityComplianceAgent
# ---------------------------------------------------------------------------

class SecurityFindings(BaseModel):
    compliant: bool = Field(..., description="True if no policy-violating CVEs found")
    violations: List[str] = Field(default_factory=list, description="Human-readable violation messages")
    vulnerabilities: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Raw vulnerability records from the MCP scan"
    )


# ---------------------------------------------------------------------------
# ModelMetrics — quality metrics from the model registry
# ---------------------------------------------------------------------------

class ModelMetrics(BaseModel):
    accuracy: float = 0.0
    f1_score: float = 0.0
    latency_p95_ms: float = 0.0


# ---------------------------------------------------------------------------
# QualityFindings — output of ModelQualityAgent
# ---------------------------------------------------------------------------

class QualityFindings(BaseModel):
    compliant: bool = Field(..., description="True if model meets all quality thresholds")
    violations: List[str] = Field(default_factory=list, description="Quality rule violations")
    metrics: ModelMetrics = Field(default_factory=ModelMetrics, description="Model performance metrics")
    data_drift: float = Field(default=0.0, description="Measured data drift score (0–1)")
    bias_detected: bool = Field(default=False, description="Whether bias was detected in the model")


# ---------------------------------------------------------------------------
# InfrastructureFindings — output of InfrastructureReadinessAgent
# ---------------------------------------------------------------------------

class InfrastructureFindings(BaseModel):
    compliant: bool = Field(..., description="True if cluster passes all resource and policy checks")
    violations: List[str] = Field(default_factory=list, description="Infrastructure violations")
    cluster_health: str = Field(default="UNKNOWN", description="Cluster health status string")
    cpu_allocation_percent: float = Field(
        default=0.0,
        description="Percentage of cluster CPU already allocated"
    )


# ---------------------------------------------------------------------------
# RiskAssessment — output of RiskAssessmentAgent
# ---------------------------------------------------------------------------

class RiskAssessment(BaseModel):
    risk_score: int = Field(..., ge=0, le=100, description="Composite risk score from 0 (safe) to 100 (critical)")
    risk_level: RiskLevel = Field(..., description="Categorical risk level: LOW, MEDIUM, or HIGH")


# ---------------------------------------------------------------------------
# PolicyDecision — output of PolicyDecisionAgent (final workflow output)
# ---------------------------------------------------------------------------

class PolicyDecision(BaseModel):
    verdict: Verdict = Field(..., description="Final deployment verdict")
    reason: str = Field(..., description="Human-readable explanation of the verdict")
    violations: List[str] = Field(default_factory=list, description="All violations collected across agents")
    risk_assessment: RiskAssessment = Field(..., description="Risk score and level from RiskAssessmentAgent")


# ---------------------------------------------------------------------------
# STATE_KEYS — canonical ctx.state key names to prevent typos
# ---------------------------------------------------------------------------

class StateKeys:
    REQUEST = "request"
    SECURITY_FINDINGS = "security_findings"
    QUALITY_FINDINGS = "quality_findings"
    INFRA_FINDINGS = "infra_findings"
    RISK_ASSESSMENT = "risk_assessment"
    FINAL_VERDICT = "final_verdict"
