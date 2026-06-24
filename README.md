# AI Platform Deployment Agent

> **Autonomous AI model governance using Google ADK, MCP FunctionTools, and Gemini 2.0 Flash.**

A hybrid cloud platform that automatically reviews AI model deployment requests through a five-agent ADK workflow — checking container security, model quality, infrastructure readiness, and enterprise policy compliance — before approving or blocking production releases.

---

## Why This Exists

Enterprise ML teams face a governance gap: there is no automated, auditable checkpoint between "model trained" and "model live in production."

Manual checklists miss CVEs, skip quality regressions, and leave no audit trail. This system replaces those checklists with a traceable, policy-enforced multi-agent review that runs in seconds and returns a fully structured verdict.

---

## Demo

```bash
uvicorn src.main:app --reload
# Open http://localhost:8000
```

Select a model → Submit → watch five agents run, the risk gauge animate, and the verdict appear.

| Scenario | Model | Result | Risk |
|---|---|---|---|
| Clean production deploy | `fraud-detection-v2` | **APPROVED** | 0/100 — LOW |
| Critical CVE in image | `customer-churn-v3` → prod | **BLOCKED** | 100/100 — HIGH |
| Poor quality to test env | `customer-churn-v3` → test | **APPROVED WITH WARNINGS** | 62/100 — MEDIUM |

---

## Architecture

```
User → FastAPI → DeploymentCoordinatorAgent (ADK Workflow)
                    │
         ┌──────────┼──────────┬──────────┬────────────┐
         ▼          ▼          ▼          ▼            ▼
      Security   Quality   Infra     Risk         Policy
      Agent      Agent     Agent     Agent        Decision
         │          │          │       (ctx.state)  Agent
         └──────────┴──────────┘                    │
              ADK FunctionTools                  LlmAgent
              ────────────────                (Gemini 2.0 Flash)
              get_container_vulnerabilities     or rule-based
              get_model_metrics                 fallback
              get_cluster_status
              get_policy_rules
                    │
              Mock MCP Server
              (synthetic JSON data)
```

---

## ADK Implementation

### 1. ADK Workflow — `coordinator.py`

```python
from google.adk.workflow import Workflow, START

DeploymentCoordinatorAgent = Workflow(
    name="DeploymentCoordinatorAgent",
    edges=[(START,
        security_compliance_agent,
        model_quality_agent,
        infrastructure_readiness_agent,
        risk_assessment_agent,
        policy_decision_agent
    )]
)
```

Five `@node` agents share state via `ctx.state` — the ADK session state dictionary. All writes are validated Pydantic models; all reads go through `Model.model_validate()`.

### 2. ADK FunctionTools — `src/tools/mcp_tools.py`

```python
from google.adk.tools import FunctionTool

get_container_vulnerabilities_tool = FunctionTool(func=get_container_vulnerabilities)
get_model_metrics_tool             = FunctionTool(func=get_model_metrics)
get_cluster_status_tool            = FunctionTool(func=get_cluster_status)
get_policy_rules_tool              = FunctionTool(func=get_policy_rules)
```

Each tool is fully typed, documented, and registered with a name and parameter schema. Every invocation is logged to `ctx.state["tool_calls"]` — 6 MCP calls per deployment review.

### 3. LLM-backed PolicyDecisionAgent — `src/agents/policy_decision.py`

```python
@node(name="PolicyDecisionAgent", rerun_on_resume=True)
async def policy_decision_agent(ctx: Context, node_input: Any):
    if _GEMINI_POLICY_AGENT:
        # Path A: Gemini reasoning
        llm_output = await ctx.run_node(_GEMINI_POLICY_AGENT, node_input=prompt)
        verdict = PolicyDecision.model_validate(json.loads(str(llm_output)))
    else:
        # Path B: deterministic fallback (used in tests)
        verdict, reason = _rule_based_verdict(request, security, quality, infra, risk)
```

Set `GOOGLE_API_KEY` to activate Gemini. The `policy_reasoning` field in the response tells you which mode ran.

---

## Mock MCP Server

`src/mcp_server.py` simulates a real enterprise MCP server backed by four fully synthetic JSON datasets:

| Data File | Contents |
|---|---|
| `data/model_registry.json` | Synthetic model accuracy, F1, latency, drift, bias |
| `data/security_scans.json` | Synthetic CVE scan results for fictional container images |
| `data/cluster_status.json` | Synthetic GKE-style cluster health and resource data |
| `data/enterprise_policies.json` | Synthetic policy rules per environment |

> **No real PII, patient records, financial data, or cloud credentials are used.**

---

## Pydantic Schemas

All inter-agent data is schema-validated (`src/models/schemas.py`):

| Schema | Owner |
|---|---|
| `DeploymentRequest` | FastAPI input + `ctx.state["request"]` |
| `SecurityFindings` | SecurityComplianceAgent |
| `QualityFindings` | ModelQualityAgent |
| `InfrastructureFindings` | InfrastructureReadinessAgent |
| `RiskAssessment` | RiskAssessmentAgent |
| `PolicyDecision` | PolicyDecisionAgent (final output) |

`StateKeys` provides typed string constants for all `ctx.state` keys.

---

## API Response

Every `POST /deploy` returns:

```json
{
  "verdict":             "APPROVED | APPROVED WITH WARNINGS | BLOCKED",
  "reason":              "...",
  "violations":          ["[Security] CVE-2024-5678 ...", "[Quality] ..."],
  "risk_assessment":     { "risk_score": 62, "risk_level": "MEDIUM" },
  "decision_confidence": 0.38,
  "agents_invoked":      ["SecurityComplianceAgent", "..."],
  "mcp_calls_made":      6,
  "recommended_actions": ["..."],
  "policy_reasoning":    "rule-based | gemini-2.0-flash",
  "tool_calls":          [...],
  "trace_events":        [...]
}
```

---

## Setup & Run

```bash
# 1. Create environment
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux

# 2. Install dependencies
pip install fastapi uvicorn pydantic pytest pytest-asyncio httpx google-adk

# 3. Run tests
pytest tests/ -v                # 9 passed

# 4. Start server
uvicorn src.main:app --reload
# Open http://localhost:8000

# 5. Run full regression
python verify_regression.py     # 3/3 scenarios passed

# 6. Optional: enable Gemini LLM reasoning
set GOOGLE_API_KEY=your-key     # Windows
uvicorn src.main:app --reload
```

---

## Test Results

```
pytest tests/ -v
────────────────────────────────────────────
test_mcp_server                    PASSED
test_mcp_function_tools_registered PASSED
test_mcp_function_tools_callable   PASSED
test_pydantic_schemas_validation   PASSED
test_state_keys_constants          PASSED
test_skills                        PASSED
test_full_workflow_standard_req    PASSED
test_full_workflow_critical_cve    PASSED
test_full_workflow_poor_metrics    PASSED
9 passed in 35s
```

---

## Project Structure

```
capstone project/
├── src/
│   ├── agents/
│   │   ├── coordinator.py        # ADK Workflow definition
│   │   ├── security.py           # SecurityComplianceAgent @node
│   │   ├── quality.py            # ModelQualityAgent @node
│   │   ├── infrastructure.py     # InfrastructureReadinessAgent @node
│   │   ├── risk_assessment.py    # RiskAssessmentAgent @node
│   │   └── policy_decision.py    # Hybrid LlmAgent + rule-based @node
│   ├── models/schemas.py         # 6 Pydantic schemas + StateKeys
│   ├── tools/mcp_tools.py        # 4 ADK FunctionTool instances
│   ├── skills/                   # Evaluation utilities
│   ├── mcp_server.py             # Mock MCP Server
│   └── main.py                   # FastAPI gateway
├── data/                         # Synthetic JSON datasets (4 files)
├── public/                       # Glassmorphism frontend
├── docs/                         # Kaggle submission materials
│   ├── project_summary.md
│   ├── architecture.md
│   ├── demo_script.md
│   ├── screenshots_checklist.md
│   └── final_submission_text.md
├── tests/test_agents.py          # 9 pytest tests
├── verify_regression.py          # Live regression script
└── pyproject.toml
```

---

##  Requirements

| Requirement | Implementation |
|---|---|
| ADK Workflow | `google.adk.workflow.Workflow` + 5 `@node` agents |
| ADK FunctionTools | 4 `FunctionTool(func=...)` instances in `src/tools/mcp_tools.py` |
| Mock MCP Server | `src/mcp_server.py` — synthetic JSON-backed tool interface |
| LLM-backed Agent | `PolicyDecisionAgent` uses `LlmAgent(model="gemini-2.0-flash")` via `ctx.run_node()` |
| Deterministic Fallback | `_rule_based_verdict()` — tests pass without API key |
| Synthetic Data Only | All 4 data files are fictional — no PII |
| Pydantic Schemas | 6 typed schemas + `StateKeys` |
| Security Checks | CVE scanning, registry allowlist, bias detection, production gate |
| Test Coverage | 9 pytest tests — tools, schemas, skills, 3 e2e scenarios |
| Frontend | Glassmorphism dark-mode UI with live risk gauge and agent timeline |
"# ai-platform-deployment-agent" 
