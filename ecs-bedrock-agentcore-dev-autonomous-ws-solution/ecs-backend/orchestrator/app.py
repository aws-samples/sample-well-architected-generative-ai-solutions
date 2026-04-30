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
from orchestrator.services.agentcore_service import invoke_agentcore_runtime, stream_agentcore_ws
from orchestrator.services.task_memory_service import save_task, get_recent_tasks
from orchestrator.services.github_service import get_repo_gitgraph
from orchestrator.services.devtool_service import enrich_task
from orchestrator.services.agentcore_memory_service import store_conversation, retrieve_context

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

    @app.get("/api/repo/graph")
    async def repo_graph(repo: str = None):
        """Fetch git graph from GitHub API and return mermaid gitgraph format."""
        repo_url = repo or os.getenv("TARGET_REPO_URL", "")
        if not repo_url:
            return {"error": "No repo URL provided", "graph": ""}
        try:
            loop = asyncio.get_event_loop()
            graph = await loop.run_in_executor(None, get_repo_gitgraph, repo_url)
            return {"graph": graph, "repo": repo_url}
        except Exception as e:
            logger.warning(f"Failed to fetch git graph: {e}")
            return {"error": str(e)[:200], "graph": ""}

    @app.get("/api/orchestrator/tasks")
    async def list_tasks(user: str = "default", limit: int = 50, repo: str = ""):
        """List recent tasks for a user from DynamoDB, optionally filtered by repo origin."""
        tasks = get_recent_tasks(user, limit)
        if repo:
            tasks = [t for t in tasks if not t.get("origin") or t.get("origin") == repo]
        return {"user": user, "tasks": tasks}

    @app.websocket("/ws")
    @app.websocket("/api/orchestrator/ws")
    async def websocket_endpoint(ws: WebSocket):
        await ws.accept()
        session_id = str(uuid.uuid4())[:8]
        session = {"id": session_id, "created": datetime.utcnow().isoformat(), "tasks": [], "history": []}
        sessions[session_id] = session
        user = "default"

        try:
            while True:
                data = await ws.receive_text()
                msg = json.loads(data)
                user_text = msg.get("text", "")
                user = msg.get("user", user) or "default"
                session["history"].append({"role": "user", "text": user_text})

                if not user_text.strip():
                    continue

                pending_done = [t for t in session["tasks"] if t["status"] == "done" and not t.get("delivered")]
                intent = await parse_intent(user_text, pending_done, msg.get("repo", ""))

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
                    # Build agent prompt: always use original user_text, add mode prefix + repo context
                    devtool = os.getenv("DEVTOOL_MODE", "false").lower() == "true"
                    prefix = "DEVTOOL MODE: You are a coding assistant. You may read/write code, run tests, use git, and create PRs. Do NOT run any AWS command that creates, modifies, or deletes infrastructure resources.\n\n" if devtool else ""
                    repo_url = msg.get("repo", "")
                    branch = msg.get("branch", "")
                    repo_ctx = ""
                    if repo_url:
                        repo_ctx = f"\nREPOSITORY CONTEXT: repo={repo_url}"
                        if branch:
                            repo_ctx += f" branch={branch}"
                        repo_ctx += "\nClone or use this repo for all code operations.\n"
                    user_input = f"{prefix}User request: {user_text}{repo_ctx}"
                    # Inject memory context from past conversations
                    try:
                        mem_ctx = await asyncio.get_event_loop().run_in_executor(
                            None, lambda: retrieve_context(user, user_text, repo_url))
                        if mem_ctx:
                            user_input += mem_ctx
                    except Exception as e:
                        logger.debug(f"Memory retrieval skipped: {e}")
                    for tool_name in tools_to_run:
                        task_id = str(uuid.uuid4())[:8]
                        task = {
                            "id": task_id, "tool": tool_name, "status": "running",
                            "input": user_text, "started": datetime.utcnow().isoformat(),
                        }
                        if repo_url:
                            enrich_task(task, repo_url, msg.get("branch", ""), msg.get("commit", ""))
                        session["tasks"].append(task)
                        save_task(user, task)
                        await ws.send_json({"type": "task_started", "task_id": task_id})
                        asyncio.create_task(_run_task(task_id, user_input, ws, session, user))
                elif ack:
                    await ws.send_json({"type": "chat", "message": ack})

        except WebSocketDisconnect:
            _save_session(session)
            del sessions[session_id]

    return app


async def _run_task(task_id: str, user_input: str, ws: WebSocket, session: dict, user: str = "default"):
    """Execute AgentCore runtime invocation via WebSocket streaming and push chunks to frontend."""
    task = next(t for t in session["tasks"] if t["id"] == task_id)
    chunks = []

    async def on_chunk(text: str):
        chunks.append(text)
        try:
            await ws.send_json({"type": "task_chunk", "task_id": task_id, "text": text})
        except Exception:
            pass  # frontend may have disconnected

    try:
        full_response = await stream_agentcore_ws(user_input, on_chunk=on_chunk)
        brief = full_response or "".join(chunks) or "(empty)"
        task["status"] = "done"
        task["result"] = {"response": brief}
        task["brief"] = brief
        task["completed"] = datetime.utcnow().isoformat()
        save_task(user, task)
        _save_session(session)
        # Store conversation in AgentCore Memory with repo context
        try:
            user_text = task.get("input", "")
            if user_text and brief:
                t_repo = task.get("origin", "")
                t_branch = task.get("branch", "")
                await asyncio.get_event_loop().run_in_executor(
                    None, lambda: store_conversation(user, session["id"], user_text, brief, t_repo, t_branch))
        except Exception as e:
            logger.debug(f"Memory store skipped: {e}")
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
        save_task(user, task)
        _save_session(session)
        await ws.send_json({"type": "task_error", "task_id": task_id, "message": f"Error: {str(e)[:200]}"})
