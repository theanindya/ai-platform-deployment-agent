# Project Summary — AI Platform Deployment Agent

## One-line Pitch

An **autonomous AI model deployment governance system** that uses a Google ADK multi-agent workflow and a Mock MCP Server to automatically review, risk-score, and approve or block production deployments — replacing manual checklist reviews with traceable, policy-enforced automation.

---

## Business Problem

Enterprise hybrid cloud teams deploying AI models face a critical gap: there is no automated, auditable gateway between "model trained" and "model in production."

Today, deployment reviewers manually check:
- Are there known CVEs in the container image?
- Does the model meet minimum accuracy and drift thresholds?
- Does the target cluster have enough capacity?
- Are monitoring and rollback configured for the environment?
- Does this deployment violate any enterprise policies?

This manual process is **slow**, **inconsistent**, and **impossible to scale** as the number of AI models in production grows. A single missed critical CVE or unreviewed bias finding can cause regulatory violations, service degradation, or reputational damage.

---

## Why Hybrid Cloud Teams Need This

| Pain Point | This System's Answer |
|---|---|
| CVE scans take days, block deployments | SecurityComplianceAgent scans in seconds and classifies by severity |
| Model quality checks are informal | ModelQualityAgent enforces minimum accuracy, F1, latency, drift, and bias thresholds |
| Infrastructure checks are manual | InfrastructureReadinessAgent validates cluster health, capacity, monitoring, and rollback |
| Risk is assessed subjectively | RiskAssessmentAgent produces an objective 0–100 score with HIGH/MEDIUM/LOW level |
| Policy decisions are ad hoc | PolicyDecisionAgent (Gemini-backed) applies enterprise rules and explains reasoning |
| No audit trail | Every agent finding, MCP tool call, and verdict is logged and returned in the API |

---

## Technology Stack

| Component | Technology |
|---|---|
| Agent Orchestration | Google ADK — `Workflow` + `@node` + `ctx.state` |
| MCP Tool Interface | Google ADK `FunctionTool` — 4 registered tools |
| LLM Reasoning | Gemini 2.0 Flash via ADK `LlmAgent` + `ctx.run_node()` |
| API Gateway | FastAPI + Uvicorn |
| Data Validation | Pydantic v2 — 6 schemas + `StateKeys` |
| Synthetic Data | 4 JSON files — model registry, CVE scans, cluster status, policies |
| Frontend | Vanilla HTML/CSS/JS — glassmorphism dark mode UI |
| Tests | pytest (9 tests, 100% pass rate) |
| IDE | Antigravity IDE (Google DeepMind) |

---

## What Makes This a Real ADK Multi-Agent System

1. **Real `Workflow`** — `google.adk.workflow.Workflow` with `START` and five `@node` agents
2. **Real `FunctionTool` instances** — all MCP calls go through `FunctionTool(func=...)` with registered names, parameter schemas, and docstrings
3. **Real `LlmAgent`** — `PolicyDecisionAgent` dynamically invokes `GeminiPolicyReviewer` via `ctx.run_node()` when an API key is available
4. **Real `ctx.state`** — shared session state carries typed, schema-validated data between all agents
5. **Real audit trail** — every tool call is logged; the event stream is captured via `runner.run_async()`

---

## Results

| Scenario | Verdict | Risk Score | Confidence | MCP Calls |
|---|---|---|---|---|
| `fraud-detection-v2` → prod | APPROVED | 0/100 (LOW) | 1.00 | 6 |
| `customer-churn-v3` → prod (critical CVEs) | BLOCKED | 100/100 (HIGH) | 0.00 | 6 |
| `customer-churn-v3` → test (poor metrics) | APPROVED WITH WARNINGS | 62/100 (MEDIUM) | 0.38 | 6 |
