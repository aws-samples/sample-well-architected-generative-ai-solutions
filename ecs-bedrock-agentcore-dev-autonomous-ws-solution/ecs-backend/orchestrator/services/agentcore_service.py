"""AgentCore Runtime invocation service with async polling."""
import json
import os
import re
import asyncio
import logging
import uuid
import boto3

logger = logging.getLogger(__name__)

AGENTCORE_REGION = os.getenv("AGENTCORE_REGION", "us-west-2")
RUNTIME_ARN = os.getenv("AGENTCORE_RUNTIME_ARN", "")
DEMO_MASK_OUTPUT = os.getenv("DEMO_MASK_OUTPUT", "false").lower() == "true"

# --- Output masking (active only when DEMO_MASK_OUTPUT=true) ---

_DEMO_DISCLAIMER = "\n\n---\n*Some resource identifiers and names have been partially masked for this demo.*"

_ID_PATTERNS = re.compile(
    r'\b('
    r'i-[0-9a-f]{8,17}|vol-[0-9a-f]{8,17}|snap-[0-9a-f]{8,17}'
    r'|sg-[0-9a-f]{8,17}|subnet-[0-9a-f]{8,17}|vpc-[0-9a-f]{8,17}'
    r'|igw-[0-9a-f]{8,17}|nat-[0-9a-f]{8,17}|eni-[0-9a-f]{8,17}'
    r'|rtb-[0-9a-f]{8,17}|acl-[0-9a-f]{8,17}|ami-[0-9a-f]{8,17}'
    r'|lt-[0-9a-f]{8,17}|[0-9]{12}'
    r')\b'
)

_NAME_PATTERNS = re.compile(
    r'(?:'
    r'(?:Name|name|InstanceName|BucketName|FunctionName|ClusterName|TableName|StackName|DBInstanceIdentifier|LogGroup|GroupName|KeyName|RoleName|TopicName|QueueName)'
    r'[\s]*[:=]\s*([A-Za-z0-9/][A-Za-z0-9._/:-]{2,})'
    r'|arn:aws:[a-z0-9-]+:[a-z0-9-]*:[0-9*]*:[a-z-]*/([A-Za-z0-9][A-Za-z0-9._/-]{2,})'
    r'|arn:aws:[a-z0-9-]+:[a-z0-9-]*:[0-9*]*:[a-z-]+:([A-Za-z0-9][A-Za-z0-9._/-]{2,})'
    r'|(?:named|called)\s+`?([A-Za-z0-9][A-Za-z0-9._/-]{2,})`?'
    r'|\*\*([A-Za-z0-9][A-Za-z0-9._/-]{2,})\*\*'
    r')'
)

_NAME_SKIP = {
    'true', 'false', 'null', 'none', 'yes', 'no', 'enabled', 'disabled',
    'active', 'inactive', 'running', 'stopped', 'terminated', 'pending',
    'available', 'error', 'healthy', 'unhealthy', 'default', 'custom',
    'public', 'private', 'internal', 'external', 'standard', 'Name',
    'the', 'and', 'for', 'with', 'from', 'that', 'this', 'are', 'was',
    'not', 'but', 'all', 'can', 'has', 'have', 'will', 'been', 'each',
    'Result', 'Here', 'following', 'below', 'above', 'Summary',
}


def _mask_output(text: str) -> str:
    """Apply ID and name masking if DEMO_MASK_OUTPUT is enabled. Returns processed text."""
    if not DEMO_MASK_OUTPUT:
        return text
    found = False

    def _replace_id(m):
        nonlocal found; found = True; v = m.group(0)
        return v[:-3] + '**' + v[-1] if len(v) >= 4 else v

    def _replace_name(m):
        nonlocal found
        name = next((g for g in m.groups() if g), None)
        if not name or name.lower() in {s.lower() for s in _NAME_SKIP} or len(name) < 3:
            return m.group(0)
        found = True
        masked = name[:3] + '***' + name[-1] if len(name) > 5 else name[:2] + '**' + name[-1]
        return m.group(0).replace(name, masked)

    text = _ID_PATTERNS.sub(_replace_id, text)
    text = _NAME_PATTERNS.sub(_replace_name, text)
    if found:
        text += _DEMO_DISCLAIMER
    return text


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
    """Invoke AgentCore runtime with async polling for long-running tasks (fallback)."""
    if not RUNTIME_ARN:
        return {"response": "AgentCore runtime ARN not configured", "error": True}

    session_id = str(uuid.uuid4())

    # Submit — retry if agent is still initializing
    for attempt in range(20):
        result = await asyncio.get_event_loop().run_in_executor(
            None, lambda: _invoke({"input": user_input}, session_id))
        status = result.get("status", "")
        if status == "initializing":
            logger.info(f"Agent initializing, retry {attempt+1}/20...")
            await asyncio.sleep(3)
            continue
        break
    else:
        return {"response": "Agent failed to start after 60 seconds"}

    task_id = result.get("task_id", "")
    sid = result.get("_session_id", session_id)

    # If immediate response (no async task), return directly
    if status != "accepted":
        return {"response": _mask_output(result.get("response", str(result)))}

    # Poll for completion
    for _ in range(60):  # up to 5 minutes (60 * 5s)
        await asyncio.sleep(5)
        try:
            poll = await asyncio.get_event_loop().run_in_executor(
                None, lambda: _invoke({"check_task": task_id}, sid))
            poll_status = poll.get("status", "")
            if poll_status == "complete":
                return {"response": _mask_output(poll.get("response", "(empty)"))}
            if poll_status not in ("processing", "accepted"):
                return {"response": _mask_output(poll.get("response", str(poll)))}
        except Exception as e:
            logger.warning(f"Poll error: {e}")

    return {"response": "Task timed out waiting for agent response"}


async def stream_agentcore_ws(user_input: str, on_chunk, on_error=None):
    """Invoke AgentCore Runtime and stream results back via polling.

    Submits the task via HTTP, then polls for completion. When the result
    arrives, streams it as a single chunk. Falls back gracefully on errors.

    Args:
        user_input: The prompt to send to the agent.
        on_chunk: async callable(text: str) invoked for each chunk.
        on_error: optional async callable(msg: str) for errors.
    Returns:
        Full response text.
    """
    if not RUNTIME_ARN:
        if on_error:
            await on_error("AgentCore runtime ARN not configured")
        return ""

    session_id = str(uuid.uuid4())

    try:
        # Submit the task — retry if agent is still initializing
        for attempt in range(20):  # retry up to ~60s for agent startup
            result = await asyncio.get_event_loop().run_in_executor(
                None, lambda: _invoke({"input": user_input}, session_id))

            status = result.get("status", "")
            if status == "initializing":
                logger.info(f"Agent initializing, retry {attempt+1}/20...")
                await asyncio.sleep(3)
                continue
            break
        else:
            msg = "Agent failed to start after 60 seconds"
            if on_error:
                await on_error(msg)
            return msg

        task_id = result.get("task_id", "")
        sid = result.get("_session_id", session_id)

        # Immediate response (no async task)
        if status != "accepted":
            resp = _mask_output(result.get("response", str(result)))
            await on_chunk(resp)
            return resp

        # Poll for completion — stream result when ready
        for i in range(90):  # up to ~5 minutes
            await asyncio.sleep(3)
            try:
                poll = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: _invoke({"check_task": task_id}, sid))
                poll_status = poll.get("status", "")
                if poll_status == "complete":
                    resp = _mask_output(poll.get("response", "(empty)"))
                    await on_chunk(resp)
                    return resp
                if poll_status not in ("processing", "accepted"):
                    resp = _mask_output(poll.get("response", str(poll)))
                    await on_chunk(resp)
                    return resp
            except Exception as e:
                logger.warning(f"Poll error: {e}")

        msg = "Task timed out waiting for agent response"
        if on_error:
            await on_error(msg)
        return msg

    except Exception as e:
        logger.warning(f"AgentCore stream failed: {e}")
        if on_error:
            await on_error(str(e)[:200])
        return ""
