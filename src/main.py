import json
import uuid
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from google.adk.runners import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.genai import types

from src.agents.coordinator import DeploymentCoordinatorAgent
from src.models import DeploymentRequest, PolicyDecision, StateKeys

app = FastAPI(
    title="AI Platform Deployment Agent Service",
    description="FastAPI service wrapper around the Google ADK Multi-Agent workflow for validating model deployments."
)

app.mount("/static", StaticFiles(directory="public"), name="static")

@app.get("/")
async def serve_index():
    return FileResponse("public/index.html")

# Initialize Session Service and Runner
session_service = InMemorySessionService()
runner = Runner(
    node=DeploymentCoordinatorAgent,
    session_service=session_service,
    app_name="AI-Platform-Deployment-Agent",
    auto_create_session=True
)



@app.post("/deploy")
async def deploy_model(request: DeploymentRequest):
    """Submits a model deployment request for review.

    Runs the request through the ADK multi-agent workflow:
    SecurityComplianceAgent -> ModelQualityAgent -> InfrastructureReadinessAgent -> RiskAssessmentAgent -> PolicyDecisionAgent.
    """
    session_id = f"session-{uuid.uuid4()}"
    request_data = request.model_dump()
    
    # Pack input payload as ADK types.Content user message
    new_message = types.Content(
        role="user",
        parts=[types.Part(text=json.dumps(request_data))]
    )
    
    final_verdict = None
    events_log = []
    
    try:
        async for event in runner.run_async(
            user_id="enterprise-platform-user",
            session_id=session_id,
            new_message=new_message
        ):
            event_dict = {
                "author": event.author,
                "node_path": event.node_info.path if event.node_info else None,
                "output": event.output,
                "error_code": event.error_code,
                "error_message": event.error_message
            }
            events_log.append(event_dict)
            
            # PolicyDecisionAgent is the terminal node yielding the final verdict payload
            if event.output is not None and isinstance(event.output, dict) and "verdict" in event.output:
                final_verdict = event.output
                
        if not final_verdict:
            # Fallback check of session events if not captured in generator loop
            session = await session_service.get_session(
                app_name=runner.app_name,
                user_id="enterprise-platform-user",
                session_id=session_id
            )
            for event in getattr(session, "events", []):
                if event.output is not None and isinstance(event.output, dict) and "verdict" in event.output:
                    final_verdict = event.output
                    break
                    
        if not final_verdict:
            raise HTTPException(
                status_code=500,
                detail="Workflow completed but failed to yield a final policy verdict."
            )
            
        # Pull the tool call log that agents wrote to ctx.state
        session = await session_service.get_session(
            app_name=runner.app_name,
            user_id="enterprise-platform-user",
            session_id=session_id
        )
        tool_calls_log = session.state.get("tool_calls", []) if session else []
        llm_used = bool(session and session.state.get("policy_llm_used"))

        # Derive summary fields from session state
        agents_invoked = [
            "SecurityComplianceAgent",
            "ModelQualityAgent",
            "InfrastructureReadinessAgent",
            "RiskAssessmentAgent",
            "PolicyDecisionAgent",
        ]
        mcp_calls_made = len(tool_calls_log)

        # decision_confidence: risk-score-based heuristic (higher score = lower confidence)
        risk_score = final_verdict.get("risk_assessment", {}).get("risk_score", 50)
        decision_confidence = round(max(0.0, 1.0 - risk_score / 100), 2)

        return {
            "session_id": session_id,
            "request_id": request.request_id,
            "verdict": final_verdict.get("verdict"),
            "reason": final_verdict.get("reason"),
            "violations": final_verdict.get("violations", []),
            "risk_assessment": final_verdict.get("risk_assessment", {}),
            "decision_confidence": decision_confidence,
            "agents_invoked": agents_invoked,
            "mcp_calls_made": mcp_calls_made,
            "recommended_actions": session.state.get("policy_recommended_actions", []) if session else [],
            "policy_reasoning": "gemini-2.0-flash" if llm_used else "rule-based",
            "tool_calls": tool_calls_log,
            "trace_events": events_log,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Deployment review workflow execution failed: {str(e)}")


@app.get("/status/{session_id}")
async def get_session_status(session_id: str):
    """Retrieves the full event log and state history for a given session ID."""
    session = await session_service.get_session(
        app_name=runner.app_name,
        user_id="enterprise-platform-user",
        session_id=session_id
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    events_log = []
    for event in session.events:
        events_log.append({
            "author": event.author,
            "node_info": event.node_info.model_dump() if event.node_info else None,
            "output": event.output,
            "state_delta": event.actions.state_delta if event.actions else None,
            "error_code": event.error_code,
            "error_message": event.error_message
        })
        
    return {
        "session_id": session_id,
        "state": session.state,
        "events": events_log
    }
