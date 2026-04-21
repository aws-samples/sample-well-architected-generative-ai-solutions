"""FastAPI app with WebSocket, Bedrock Claude intent parsing, and AgentCore Runtime invocation."""
import asyncio
import json
import uuid
import os
import logging
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from orchestrator.services.intent_service import parse_intent
from orchestrator.services.agentcore_service import invoke_agentcore_runtime

logger = logging.getLogger(__name__)

sessions: dict[str, dict] = {}


def create_orchestrator_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(title="AgentCore Long-Running Orchestrator", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def health():
        return {"status": "healthy", "mode": "agentcore-longrun", "timestamp": datetime.utcnow().isoformat()}

    @app.get("/")
    @app.get("/api/orchestrator")
    async def root():
        return {"service": "agentcore-longrun-orchestrator", "version": "0.1.0"}

    @app.websocket("/ws")
    @app.websocket("/api/orchestrator/ws")
    async def websocket_endpoint(ws: WebSocket):
        await ws.accept()
        session_id = str(uuid.uuid4())[:8]
        session = {"id": session_id, "tasks": [], "history": []}
        sessions[session_id] = session

        try:
            while True:
                data = await ws.receive_text()
                msg = json.loads(data)
                user_text = msg.get("text", "")
                session["history"].append({"role": "user", "text": user_text})

                pending_done = [t for t in session["tasks"] if t["status"] == "done" and not t.get("delivered")]
                intent = await parse_intent(user_text, pending_done)

                if intent.get("follow_up"):
                    if pending_done:
                        task = pending_done[0]
                        task["delivered"] = True
                        if intent["follow_up"] == "detail":
                            await ws.send_json({"type": "detail", "task_id": task["id"], "message": "Here's the full detail:", "data": task["result"]})
                        else:
                            await ws.send_json({"type": "brief", "task_id": task["id"], "message": task["brief"]})
                    continue

                tools_to_run = intent.get("tools", [])
                ack = intent.get("ack", "")

                if tools_to_run:
                    await ws.send_json({"type": "ack", "message": ack})
                    user_input = intent.get("input", user_text)
                    for tool_name in tools_to_run:
                        task_id = str(uuid.uuid4())[:8]
                        task = {"id": task_id, "tool": tool_name, "status": "running", "started": datetime.utcnow().isoformat()}
                        session["tasks"].append(task)
                        asyncio.create_task(_run_task(task_id, user_input, ws, session))
                elif ack:
                    await ws.send_json({"type": "chat", "message": ack})

        except WebSocketDisconnect:
            del sessions[session_id]

    return app


async def _run_task(task_id: str, user_input: str, ws: WebSocket, session: dict):
    """Execute AgentCore runtime invocation and push result."""
    task = next(t for t in session["tasks"] if t["id"] == task_id)
    try:
        result = await invoke_agentcore_runtime(user_input)
        brief = result.get("response", str(result))
        task["status"] = "done"
        task["result"] = result
        task["brief"] = brief
        await ws.send_json({
            "type": "task_complete",
            "task_id": task_id,
            "brief": brief,
            "message": f"Result ready:\n\n{brief}\n\nWould you like the full detail?",
        })
    except Exception as e:
        task["status"] = "error"
        await ws.send_json({"type": "task_error", "task_id": task_id, "message": f"Error: {str(e)[:200]}"})
