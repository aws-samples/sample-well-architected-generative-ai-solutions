"""AgentCore Runtime invocation service with async polling."""
import json
import os
import asyncio
import logging
import uuid
import boto3

logger = logging.getLogger(__name__)

AGENTCORE_REGION = os.getenv("AGENTCORE_REGION", "us-west-2")
RUNTIME_ARN = os.getenv("AGENTCORE_RUNTIME_ARN", "")


def _get_client():
    return boto3.client("bedrock-agentcore", region_name=AGENTCORE_REGION)


def _invoke(payload: dict, session_id: str = None) -> dict:
    """Single invoke call, returns parsed response."""
    client = _get_client()
    kwargs = {
        "agentRuntimeArn": RUNTIME_ARN,
        "payload": json.dumps(payload).encode(),
        "contentType": "application/json",
        "accept": "application/json",
    }
    if session_id:
        kwargs["runtimeSessionId"] = session_id
    resp = client.invoke_agent_runtime(**kwargs)
    body = resp["response"].read().decode()
    session = resp.get("runtimeSessionId", session_id)
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        data = {"response": body}
    return {**data, "_session_id": session}


async def invoke_agentcore_runtime(user_input: str) -> dict:
    """Invoke AgentCore runtime with async polling for long-running tasks."""
    if not RUNTIME_ARN:
        return {"response": "AgentCore runtime ARN not configured", "error": True}

    session_id = str(uuid.uuid4())

    # First call: submit the task
    result = await asyncio.get_event_loop().run_in_executor(
        None, lambda: _invoke({"input": user_input}, session_id))

    status = result.get("status", "")
    task_id = result.get("task_id", "")
    sid = result.get("_session_id", session_id)

    # If immediate response (no async task), return directly
    if status != "accepted":
        return {"response": result.get("response", str(result))}

    # Poll for completion
    for _ in range(60):  # up to 5 minutes (60 * 5s)
        await asyncio.sleep(5)
        try:
            poll = await asyncio.get_event_loop().run_in_executor(
                None, lambda: _invoke({"check_task": task_id}, sid))
            poll_status = poll.get("status", "")
            if poll_status == "complete":
                return {"response": poll.get("response", "(empty)")}
            if poll_status not in ("processing", "accepted"):
                return {"response": poll.get("response", str(poll))}
        except Exception as e:
            logger.warning(f"Poll error: {e}")

    return {"response": "Task timed out waiting for agent response"}
