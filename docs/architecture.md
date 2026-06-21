# Architecture — AI Platform Deployment Agent

## System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        User / Browser                               │
│              http://localhost:8000  (Glassmorphism UI)              │
└───────────────────────────┬─────────────────────────────────────────┘
                            │ POST /deploy (DeploymentRequest JSON)
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     FastAPI Gateway (main.py)                       │
│   • Validates request via Pydantic DeploymentRequest schema         │
│   • Wraps payload in types.Content for ADK                         │
│   • Calls runner.run_async() → async event stream                   │
│   • Returns structured JSON with all response fields                │
└───────────────────────────┬─────────────────────────────────────────┘
                            │ ADK Runner.run_async()
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│            DeploymentCoordinatorAgent  (ADK Workflow)               │
│            google.adk.workflow.Workflow  — coordinator.py           │
│                                                                     │
│   edges = [(START, sec, quality, infra, risk, policy)]             │
└──┬──────────────┬──────────────┬──────────────┬──────────────┬──────┘
   │              │              │              │              │
   ▼              ▼              ▼              ▼              ▼
┌──────┐      ┌──────┐      ┌──────┐      ┌──────┐      ┌──────────┐
│Secu- │      │Model │      │Infra-│      │Risk  │      │Policy    │
│rity  │      │Qual- │      │struc-│      │Asses-│      │Decision  │
│Comp- │      │ity   │      │ture  │      │sment │      │Agent     │
│liance│      │Agent │      │Readi-│      │Agent │      │          │
│Agent │      │      │      │ness  │      │      │      │LlmAgent  │
│      │      │      │      │Agent │      │      │      │or rules  │
└──┬───┘      └──┬───┘      └──┬───┘      └──┬───┘      └────┬─────┘
   │  ADK         │  ADK        │  ADK         │              │
   │  tools       │  tools      │  tools       │ reads        │
   ▼              ▼             ▼              │ ctx.state    │
┌─────────────────────────────────────────────┤              │
│         ADK FunctionTools (mcp_tools.py)    │              │
│                                             │              │
│  get_container_vulnerabilities ────────────►│              │
│  get_model_metrics             ────────────►│              │
│  get_cluster_status            ────────────►│              │
│  get_policy_rules              ────────────►│              │
└─────────────────────────────────────────────┘              │
                    │                                         │
                    ▼                                         ▼
┌──────────────────────────────────┐     ┌────────────────────────────┐
│    Mock MCP Server (mcp_server)  │     │  Gemini 2.0 Flash          │
│                                  │     │  (LlmAgent via             │
│  data/model_registry.json        │     │   ctx.run_node)            │
│  data/security_scans.json        │     │                            │
│  data/cluster_status.json        │     │  Fallback: rule-based      │
│  data/enterprise_policies.json   │     │  _rule_based_verdict()     │
│                                  │     │                            │
│  [SYNTHETIC DATA ONLY]           │     │  Output: PolicyDecision    │
└──────────────────────────────────┘     └────────────────────────────┘
```

---

## ADK Workflow Node Sequence

```
START
  │
  ├─► SecurityComplianceAgent
  │     Reads: node_input (ADK Content)
  │     Tools: get_container_vulnerabilities, get_policy_rules
  │     Writes: ctx.state["request"], ctx.state["security_findings"]
  │
  ├─► ModelQualityAgent
  │     Reads: ctx.state["request"]
  │     Tools: get_model_metrics, get_policy_rules
  │     Writes: ctx.state["quality_findings"]
  │
  ├─► InfrastructureReadinessAgent
  │     Reads: ctx.state["request"]
  │     Tools: get_cluster_status, get_policy_rules
  │     Writes: ctx.state["infra_findings"]
  │
  ├─► RiskAssessmentAgent
  │     Reads: ctx.state["security_findings"]
  │             ctx.state["quality_findings"]
  │             ctx.state["infra_findings"]
  │     Writes: ctx.state["risk_assessment"]
  │
  └─► PolicyDecisionAgent  (async node)
        Reads: all ctx.state findings
        Path A (API key): ctx.run_node(GeminiPolicyReviewer)
        Path B (no key):  _rule_based_verdict()
        Writes: ctx.state["final_verdict"]
```

---

## ctx.state Data Flow (Pydantic Schemas)

```
ctx.state["request"]            ← DeploymentRequest
ctx.state["security_findings"]  ← SecurityFindings
ctx.state["quality_findings"]   ← QualityFindings
ctx.state["infra_findings"]     ← InfrastructureFindings
ctx.state["risk_assessment"]    ← RiskAssessment
ctx.state["final_verdict"]      ← PolicyDecision
ctx.state["tool_calls"]         ← List[ToolCallRecord]  (audit log)
ctx.state["policy_llm_used"]    ← bool
```

All schemas live in `src/models/schemas.py`. `StateKeys` provides typed constants.

---

## ADK FunctionTools → Mock MCP Server

```
FunctionTool                      Mock MCP Server method
─────────────────────────────     ─────────────────────────────────────
get_container_vulnerabilities  →  MockMCPServer.get_container_vulnerabilities()
get_model_metrics              →  MockMCPServer.get_model_metrics()
get_cluster_status             →  MockMCPServer.get_cluster_status()
get_policy_rules               →  MockMCPServer.get_policy_rules()
```

Each `FunctionTool` is registered with:
- **Name**: extracted from function name
- **Description**: from docstring (used by LLM for tool selection)
- **Parameter schema**: from type annotations

---

## PolicyDecisionAgent — Hybrid Decision Engine

```
policy_decision_agent (async @node)
        │
        ├── _GEMINI_POLICY_AGENT available? (GOOGLE_API_KEY set)
        │         │
        │         YES ──► await ctx.run_node(GeminiPolicyReviewer, prompt_json)
        │         │              │
        │         │              ├── LlmAgent sends findings to Gemini 2.0 Flash
        │         │              ├── Gemini returns JSON {verdict, reason, actions}
        │         │              └── PolicyDecision.model_validate(response)
        │         │
        │         NO (or LLM fails)
        │         │
        └── _rule_based_verdict(request, security, quality, infra, risk)
                  │
                  ├── risk_level == HIGH → BLOCKED
                  ├── env == prod AND violations > 0 → BLOCKED
                  ├── "critical" in violations → BLOCKED
                  ├── violations > 0 OR risk == MEDIUM → APPROVED WITH WARNINGS
                  └── else → APPROVED
```

---

## API Response Schema

```json
{
  "session_id": "session-<uuid>",
  "request_id": "req_001",
  "verdict": "APPROVED | APPROVED WITH WARNINGS | BLOCKED",
  "reason": "<explanation>",
  "violations": ["[Security] ...", "[Quality] ...", "[Infrastructure] ..."],
  "risk_assessment": { "risk_score": 0, "risk_level": "LOW" },
  "decision_confidence": 1.0,
  "agents_invoked": ["SecurityComplianceAgent", "ModelQualityAgent",
                     "InfrastructureReadinessAgent", "RiskAssessmentAgent",
                     "PolicyDecisionAgent"],
  "mcp_calls_made": 6,
  "recommended_actions": [],
  "policy_reasoning": "rule-based | gemini-2.0-flash",
  "tool_calls": [
    {
      "tool": "get_container_vulnerabilities",
      "agent": "SecurityComplianceAgent",
      "args": { "image_uri": "gcr.io/enterprise-platform/fraud-detection:v2" },
      "result_summary": { "scan_status": "COMPLETED", "vuln_count": 0 }
    }
  ],
  "trace_events": [...]
}
```

---

## Directory Structure

```
capstone project/
├── src/
│   ├── agents/
│   │   ├── coordinator.py       # ADK Workflow definition
│   │   ├── security.py          # SecurityComplianceAgent @node
│   │   ├── quality.py           # ModelQualityAgent @node
│   │   ├── infrastructure.py    # InfrastructureReadinessAgent @node
│   │   ├── risk_assessment.py   # RiskAssessmentAgent @node
│   │   └── policy_decision.py   # PolicyDecisionAgent (async @node + LlmAgent)
│   ├── models/
│   │   └── schemas.py           # 6 Pydantic schemas + StateKeys + enums
│   ├── tools/
│   │   └── mcp_tools.py         # 4 ADK FunctionTool instances + MCP_TOOLS registry
│   ├── skills/
│   │   ├── policy_checker.py    # registry + CVE evaluation
│   │   ├── quality_checker.py   # accuracy/F1/drift/bias thresholds
│   │   └── resource_validator.py# CPU/memory/GPU capacity checks
│   ├── utils/helpers.py         # ADK Content → dict parser
│   ├── mcp_server.py            # Mock MCP Server (JSON-backed)
│   └── main.py                  # FastAPI gateway
├── data/
│   ├── model_registry.json      # Synthetic model metrics
│   ├── security_scans.json      # Synthetic CVE scan data
│   ├── cluster_status.json      # Synthetic cluster health
│   ├── enterprise_policies.json # Synthetic policy rules
│   └── deployment_requests/
│       ├── req_001_standard.json
│       ├── req_002_critical_cve.json
│       └── req_003_poor_metrics.json
├── public/                      # Glassmorphism frontend (HTML/CSS/JS)
├── docs/                        # Kaggle submission materials
├── tests/test_agents.py         # 9 pytest tests
├── verify_regression.py         # Full regression verification script
└── pyproject.toml
```
