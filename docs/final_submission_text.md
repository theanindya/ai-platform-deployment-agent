# Final Submission Text — AI Platform Deployment Agent

*Copy this text into your Kaggle submission form / notebook description.*

---

## Project Title

**AI Platform Deployment Agent — Autonomous Model Governance with Google ADK, MCP, and Gemini**

---

## Short Description (≤ 280 characters)

> A multi-agent AI deployment governance system using Google ADK Workflow, ADK FunctionTools, a Mock MCP Server, and a Gemini-backed PolicyDecisionAgent. Automatically reviews, risk-scores, and approves or blocks AI model deployments.

---

## Full Submission Description

### The Business Problem

Enterprise hybrid cloud teams deploying AI models lack an automated, auditable gateway between model training and production release. Today, deployment reviewers manually check container CVEs, model quality metrics, cluster capacity, and enterprise policy compliance — a process that is slow, inconsistent, and impossible to scale as AI portfolios grow.

A single missed critical CVE or unreviewed bias finding can cause regulatory violations, service degradation, or reputational damage. This project replaces that manual process with an autonomous, multi-agent governance system.

---

### Solution: AI Platform Deployment Agent

This system uses a **Google ADK multi-agent workflow** to automatically review every deployment request through five specialist agents, each querying a Mock MCP Server via registered **ADK FunctionTools**. The final verdict is produced by a **Gemini-backed `PolicyDecisionAgent`** with a deterministic fallback for offline use.

**Every API response includes:**
- `verdict` — APPROVED, APPROVED WITH WARNINGS, or BLOCKED
- `reason` — plain-language explanation of the decision
- `violations` — tagged list of policy violations from all agents
- `risk_assessment` — composite risk score (0–100) and level (LOW/MEDIUM/HIGH)
- `decision_confidence` — 1 − (risk_score / 100)
- `agents_invoked` — all 5 agent names
- `mcp_calls_made` — total ADK FunctionTool calls made
- `policy_reasoning` — `"gemini-2.0-flash"` or `"rule-based"`

---

### ADK Workflow

The orchestrator is a real `google.adk.workflow.Workflow` named `DeploymentCoordinatorAgent`. It runs five `@node` agents in sequence:

| Agent | Responsibility |
|---|---|
| SecurityComplianceAgent | CVE scanning, registry allowlist enforcement |
| ModelQualityAgent | Accuracy, F1, latency, data drift, bias threshold checks |
| InfrastructureReadinessAgent | Cluster health, CPU/memory/GPU capacity, monitoring, rollback |
| RiskAssessmentAgent | Composite 0–100 risk score from all upstream findings |
| PolicyDecisionAgent | Final verdict — Gemini LLM reasoning or deterministic rules |

All inter-agent data flows through typed, schema-validated `ctx.state` using 6 Pydantic models and `StateKeys` constants.

---

### MCP FunctionTools

All MCP calls are registered as **ADK `FunctionTool` instances** in `src/tools/mcp_tools.py`:

```python
get_container_vulnerabilities_tool = FunctionTool(func=get_container_vulnerabilities)
get_model_metrics_tool             = FunctionTool(func=get_model_metrics)
get_cluster_status_tool            = FunctionTool(func=get_cluster_status)
get_policy_rules_tool              = FunctionTool(func=get_policy_rules)
```

Each tool is fully typed, documented, and registered with a name and parameter schema. Every invocation is logged to `ctx.state["tool_calls"]` for a complete audit trail. A typical deployment triggers **6 MCP tool calls** across the three data-fetching agents.

---

### LLM-Backed PolicyDecisionAgent with Fallback

`PolicyDecisionAgent` is an async `@node` that supports two modes:

**Mode A — Gemini LLM** (when `GOOGLE_API_KEY` is set):
- Dynamically invokes `GeminiPolicyReviewer` (`LlmAgent`) via `ctx.run_node()`
- Sends a structured JSON prompt with all upstream findings
- Gemini 2.0 Flash returns a JSON verdict with natural-language reasoning and recommended remediation actions
- Response is validated via `PolicyDecision.model_validate()`

**Mode B — Deterministic Rules** (no API key):
- Applies ordered policy rules in pure Python
- Guarantees reproducible results in CI/local testing without credentials

---

### Security Checks

| Check | Agent | Data Source |
|---|---|---|
| CVE severity vs. environment maximum | SecurityComplianceAgent | `data/security_scans.json` |
| Container registry allowlist | SecurityComplianceAgent | `data/enterprise_policies.json` |
| Minimum F1 score per environment | ModelQualityAgent | `data/model_registry.json` |
| Maximum data drift threshold | ModelQualityAgent | `data/model_registry.json` |
| Bias detection flag | ModelQualityAgent | `data/model_registry.json` |
| Cluster health status (HEALTHY/DEGRADED) | InfrastructureReadinessAgent | `data/cluster_status.json` |
| Monitoring required for environment | InfrastructureReadinessAgent | `data/enterprise_policies.json` |
| Rollback strategy required | InfrastructureReadinessAgent | `data/enterprise_policies.json` |
| Zero-violation production gate | PolicyDecisionAgent | All upstream findings |

---

### Synthetic Data Only

All data is **entirely synthetic** — no real PII, patient records, financial data, or cloud credentials are used:

- `data/model_registry.json` — synthetic model performance metrics
- `data/security_scans.json` — synthetic CVE scan results (fictional registry)
- `data/cluster_status.json` — synthetic GKE-style cluster health data
- `data/enterprise_policies.json` — synthetic per-environment policy rules

---

### Test Results

```
pytest tests/ -v
9 passed in 35s
```

Tests cover: MCP server, ADK FunctionTool registration and callability, Pydantic schema validation, StateKeys constants, skill helpers, and 3 full end-to-end workflow scenarios.

**Regression verification** (all 3 scenarios via live API):
```
Scenario 1 — Standard (APPROVED):          risk=0,   confidence=1.00, mcp_calls=6  [PASS]
Scenario 2 — Critical CVE (BLOCKED):       risk=100, confidence=0.00, mcp_calls=6  [PASS]
Scenario 3 — Poor Metrics (WARNINGS):      risk=62,  confidence=0.38, mcp_calls=6  [PASS]
3/3 scenarios passed
```

---

### How to Run

```bash
# Setup
python -m venv .venv
.venv\Scripts\activate
pip install fastapi uvicorn pydantic pytest pytest-asyncio httpx google-adk

# Run tests
pytest tests/ -v

# Start server
uvicorn src.main:app --reload
# Open http://localhost:8000

# Run regression
python verify_regression.py

# Enable Gemini LLM reasoning (optional)
set GOOGLE_API_KEY=your-key
uvicorn src.main:app --reload
```

---

### Technologies Used

- **Google ADK** — `Workflow`, `@node`, `FunctionTool`, `LlmAgent`, `ctx.run_node()`, `InMemorySessionService`, `Runner`
- **Gemini 2.0 Flash** — LLM reasoning for PolicyDecisionAgent
- **FastAPI + Uvicorn** — REST API gateway
- **Pydantic v2** — typed schemas for all inter-agent state
- **Pytest** — 9 automated tests
- **Vanilla HTML/CSS/JS** — glassmorphism dark-mode frontend
- **Antigravity IDE** — developed using Google DeepMind's AI coding assistant

---

### GitHub Repository Structure

```
capstone project/
├── src/agents/          # 5 ADK @node agents
├── src/models/          # Pydantic schemas
├── src/tools/           # ADK FunctionTool wrappers
├── src/skills/          # Evaluation utilities
├── src/mcp_server.py    # Mock MCP Server
├── src/main.py          # FastAPI gateway
├── data/                # Synthetic JSON data files
├── public/              # Frontend UI
├── docs/                # Kaggle submission materials
└── tests/               # pytest test suite
```
