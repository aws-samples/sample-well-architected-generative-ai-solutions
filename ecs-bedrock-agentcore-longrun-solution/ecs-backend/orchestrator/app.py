"""FastAPI app with WebSocket, Bedrock Claude intent parsing, and AgentCore Runtime invocation."""
import asyncio
import json
import uuid
import os
import logging
from datetime import datetime

import boto3
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from orchestrator.services.intent_service import parse_intent
from orchestrator.services.agentcore_service import invoke_agentcore_runtime

logger = logging.getLogger(__name__)

sessions: dict[str, dict] = {}

TASK_LOG_BUCKET = os.getenv("TASK_LOG_BUCKET", "")
TASK_LOG_PREFIX = os.getenv("TASK_LOG_PREFIX", "sessions")
_s3 = boto3.client("s3") if TASK_LOG_BUCKET else None


def _save_session(session: dict):
    """Persist session data to S3 as JSON."""
    if not _s3:
        return
    try:
        key = f"{TASK_LOG_PREFIX}/{session['created'][:10]}/{session['id']}.json"
        _s3.put_object(
            Bucket=TASK_LOG_BUCKET, Key=key,
            Body=json.dumps(session, default=str),
            ContentType="application/json",
        )
    except Exception as e:
        logger.warning(f"Failed to save session to S3: {e}")


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

    @app.get("/api/orchestrator/sessions")
    async def list_sessions(date: str = None):
        """List session logs from S3. Optional ?date=2026-04-23 filter."""
        if not _s3:
            return {"sessions": [], "error": "TASK_LOG_BUCKET not configured"}
        prefix = f"{TASK_LOG_PREFIX}/{date}/" if date else f"{TASK_LOG_PREFIX}/"
        try:
            resp = _s3.list_objects_v2(Bucket=TASK_LOG_BUCKET, Prefix=prefix)
            items = []
            for obj in resp.get("Contents", []):
                items.append({"key": obj["Key"], "modified": obj["LastModified"].isoformat(), "size": obj["Size"]})
            return {"sessions": sorted(items, key=lambda x: x["modified"], reverse=True)}
        except Exception as e:
            return {"sessions": [], "error": str(e)[:200]}

    @app.get("/api/orchestrator/sessions/{session_id}")
    async def get_session(session_id: str, date: str = None):
        """Fetch a specific session log from S3."""
        if not _s3:
            return {"error": "TASK_LOG_BUCKET not configured"}
        try:
            if date:
                key = f"{TASK_LOG_PREFIX}/{date}/{session_id}.json"
            else:
                # search recent dates
                resp = _s3.list_objects_v2(Bucket=TASK_LOG_BUCKET, Prefix=f"{TASK_LOG_PREFIX}/", MaxKeys=1000)
                key = next((o["Key"] for o in resp.get("Contents", []) if session_id in o["Key"]), None)
                if not key:
                    return {"error": "Session not found"}
            obj = _s3.get_object(Bucket=TASK_LOG_BUCKET, Key=key)
            return json.loads(obj["Body"].read())
        except Exception as e:
            return {"error": str(e)[:200]}

    @app.websocket("/ws")
    @app.websocket("/api/orchestrator/ws")
    async def websocket_endpoint(ws: WebSocket):
        await ws.accept()
        session_id = str(uuid.uuid4())[:8]
        session = {"id": session_id, "created": datetime.utcnow().isoformat(), "tasks": [], "history": []}
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
                        await ws.send_json({"type": "task_started", "task_id": task_id})
                        asyncio.create_task(_run_task(task_id, user_input, ws, session))
                elif ack:
                    await ws.send_json({"type": "chat", "message": ack})

        except WebSocketDisconnect:
            _save_session(session)
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
        task["completed"] = datetime.utcnow().isoformat()
        _save_session(session)
        await ws.send_json({
            "type": "task_complete",
            "task_id": task_id,
            "brief": brief,
            "message": f"Result ready:\n\n{brief}\n\nWould you like the full detail?",
        })
    except Exception as e:
        task["status"] = "error"
        task["error"] = str(e)[:200]
        task["completed"] = datetime.utcnow().isoformat()
        _save_session(session)
        await ws.send_json({"type": "task_error", "task_id": task_id, "message": f"Error: {str(e)[:200]}"})
