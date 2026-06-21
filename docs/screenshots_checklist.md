# Screenshots Checklist — Kaggle Submission

Capture these screenshots before submitting. Use a 1280×800 or wider browser window.
Save all screenshots in `docs/screenshots/`.

---

## 1. UI — Empty Form (Home State)
**File:** `01_ui_home.png`

- [ ] Open `http://localhost:8000`
- [ ] Form is visible with all dropdowns populated
- [ ] Dark glassmorphism theme visible
- [ ] No results panel shown yet

---

## 2. Scenario 1 — APPROVED Result
**File:** `02_approved_result.png`

Steps:
- [ ] Select model: `fraud-detection-v2`
- [ ] Environment: Production
- [ ] Cluster: k8s-cluster-prod-1
- [ ] Monitoring: enabled
- [ ] Rollback: rolling-update
- [ ] Submit and wait

Capture when:
- [ ] **APPROVED** badge visible in green
- [ ] Risk gauge shows **0 / 100** in green
- [ ] Timeline shows all 5 agents completed
- [ ] Violations table shows "No violations found"
- [ ] `decision_confidence: 1.0` visible

---

## 3. Scenario 2 — BLOCKED Result
**File:** `03_blocked_result.png`

Steps:
- [ ] Select model: `customer-churn-v3`
- [ ] Environment: Production
- [ ] Cluster: k8s-cluster-prod-1
- [ ] Submit

Capture when:
- [ ] **BLOCKED** badge visible in red
- [ ] Risk gauge shows **100 / 100** in red
- [ ] Violations table lists CVE violations with IDs
- [ ] `decision_confidence: 0.0` visible

---

## 4. Scenario 3 — APPROVED WITH WARNINGS Result
**File:** `04_warnings_result.png`

Steps:
- [ ] Select model: `customer-churn-v3`
- [ ] Environment: Testing
- [ ] Cluster: k8s-cluster-staging-1
- [ ] Submit

Capture when:
- [ ] **APPROVED WITH WARNINGS** badge visible in amber/orange
- [ ] Risk gauge shows **62 / 100** in amber
- [ ] Violations table shows quality violations
- [ ] `decision_confidence: 0.38` visible

---

## 5. API Response (FastAPI Docs)
**File:** `05_api_docs.png`

- [ ] Open `http://localhost:8000/docs`
- [ ] Expand the `POST /deploy` endpoint
- [ ] Show the request schema with all fields
- [ ] Show the response schema

---

## 6. Pytest Output
**File:** `06_pytest_passing.png`

Run: `pytest tests/ -v`

Capture:
- [ ] All 9 tests listed by name
- [ ] All showing `PASSED`
- [ ] Final line: `9 passed`
- [ ] Terminal window clearly visible

---

## 7. Project Structure (VS Code / terminal)
**File:** `07_project_structure.png`

- [ ] Show the `src/` folder tree with all agent files
- [ ] `src/models/schemas.py` visible
- [ ] `src/tools/mcp_tools.py` visible
- [ ] `data/` folder with JSON files visible

---

## 8. Architecture Diagram
**File:** `08_architecture.png`

- [ ] Take a screenshot of the architecture PNG already in the artifacts directory
- [ ] Or render the `architecture.mmd` Mermaid file

---

## 9. Code — coordinator.py (ADK Workflow)
**File:** `09_coordinator_code.png`

- [ ] Open `src/agents/coordinator.py` in editor
- [ ] Show the full `Workflow(...)` definition
- [ ] Syntax highlighting visible

---

## 10. Code — mcp_tools.py (FunctionTools)
**File:** `10_mcp_tools_code.png`

- [ ] Open `src/tools/mcp_tools.py` in editor
- [ ] Show the `FunctionTool(func=...)` lines
- [ ] Ideally show 2-3 tool definitions

---

## 11. Code — policy_decision.py (LlmAgent)
**File:** `11_policy_llm_code.png`

- [ ] Open `src/agents/policy_decision.py` in editor
- [ ] Show `_build_llm_agent()` function with `LlmAgent(model="gemini-2.0-flash")`
- [ ] Show `await ctx.run_node(_GEMINI_POLICY_AGENT, ...)` call

---

## Submission Order

Include screenshots in this order in your Kaggle notebook or submission post:
1. `08_architecture.png` — system overview
2. `01_ui_home.png` — frontend
3. `02_approved_result.png`
4. `03_blocked_result.png`
5. `04_warnings_result.png`
6. `06_pytest_passing.png` — proof of tests
7. `09_coordinator_code.png` — ADK Workflow code
8. `10_mcp_tools_code.png` — FunctionTool code
9. `11_policy_llm_code.png` — LlmAgent code
10. `05_api_docs.png` — API reference
