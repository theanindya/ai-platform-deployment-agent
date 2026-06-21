# 2-Minute Demo Script — AI Platform Deployment Agent

**Format:** Screen recording or live demo  
**Total time:** ~2 minutes  
**Audience:** Kaggle reviewers, ML engineers, platform teams

---

## [0:00 – 0:15] Hook: The Problem

> *"Every time an AI model is deployed to production, someone has to manually check: are there CVEs in the image? Does the model still pass quality thresholds? Is the cluster healthy? Does this violate any enterprise policies?"*
>
> *"This is slow, inconsistent, and impossible to audit. This project automates that entire review — using a Google ADK multi-agent workflow backed by a Mock MCP Server."*

**Show:** The running UI at `http://localhost:8000`

---

## [0:15 – 0:40] Demo: Scenario 1 — APPROVED

> *"Let's deploy our best model — fraud-detection-v2 — to production."*

**Action steps:**
1. Select **fraud-detection-v2** from the Model Name dropdown
   - Version auto-fills to `2.0.0`
   - Container image auto-fills to `gcr.io/enterprise-platform/fraud-detection:v2`
2. Set Environment → **Production**
3. Set Target Cluster → **k8s-cluster-prod-1**
4. Enable **Monitoring** toggle
5. Set Rollback Strategy → **Rolling Update**
6. Click **Submit Deployment Request**

> *"Five agents run in sequence — Security, Quality, Infrastructure, Risk Assessment, and Policy Decision. Each one calls ADK FunctionTools to query the Mock MCP Server."*

**Point out on screen:**
- Agent timeline populating one by one
- Risk gauge animating to 0/100 — LOW risk
- **APPROVED** badge appearing in green
- Violations table: empty

---

## [0:40 – 1:10] Demo: Scenario 2 — BLOCKED

> *"Now let's try to push a model with known critical CVEs into production."*

**Action steps:**
1. Select **customer-churn-v3** from the Model Name dropdown
2. Set Environment → **Production**
3. Set Target Cluster → **k8s-cluster-prod-1**
4. Click **Submit**

> *"The SecurityComplianceAgent finds two critical CVEs — CVE-2024-5678 in glibc and CVE-2024-9999 in python-pip. The RiskAssessmentAgent scores this at 100/100. The PolicyDecisionAgent blocks it immediately."*

**Point out on screen:**
- Risk gauge animating to 100/100 — HIGH risk — turning red
- **BLOCKED** badge in red
- Violations table: 2 security violations listed with CVE IDs

---

## [1:10 – 1:35] Demo: Scenario 3 — APPROVED WITH WARNINGS

> *"Finally, let's push the churn model to test — not production — to see a warnings case."*

**Action steps:**
1. Keep **customer-churn-v3** selected
2. Change Environment → **Testing**
3. Set Target Cluster → **k8s-cluster-staging-1**
4. Click **Submit**

> *"The model has 15% data drift and bias detected, which violates quality thresholds. But it's not production, and no critical CVEs block it outright. Risk score: 62. The result is Approved With Warnings — the team can proceed, but must review the quality violations before promoting."*

**Point out on screen:**
- Risk gauge at 62/100 — MEDIUM — in amber
- **APPROVED WITH WARNINGS** badge in amber
- Violations table: quality violations listed

---

## [1:35 – 2:00] Code Callout

> *"Behind the UI, this is a real Google ADK Workflow — not just a Python pipeline."*

**Open `src/agents/coordinator.py`:**
```python
DeploymentCoordinatorAgent = Workflow(
    name="DeploymentCoordinatorAgent",
    edges=[(START, security_compliance_agent, model_quality_agent,
            infrastructure_readiness_agent, risk_assessment_agent,
            policy_decision_agent)]
)
```

> *"Each agent calls ADK FunctionTools to query the Mock MCP Server:"*

**Open `src/tools/mcp_tools.py`:**
```python
get_container_vulnerabilities_tool = FunctionTool(func=get_container_vulnerabilities)
get_model_metrics_tool             = FunctionTool(func=get_model_metrics)
```

> *"And the PolicyDecisionAgent can use Gemini 2.0 Flash for reasoning when an API key is set — with a deterministic fallback so tests always pass without credentials."*

> *"9 tests, all passing. All synthetic data. All ADK-native. Thank you."*

---

## Terminal commands to have ready

```bash
# Window 1 — server
uvicorn src.main:app --reload

# Window 2 — tests (show during code callout)
pytest tests/ -v

# Window 3 — regression
python verify_regression.py
```
