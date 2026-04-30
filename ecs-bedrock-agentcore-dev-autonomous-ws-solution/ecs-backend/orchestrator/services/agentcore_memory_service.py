"""AgentCore Memory service — store conversation events and retrieve context."""
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

MEMORY_ID = os.getenv("AGENTCORE_MEMORY_ID", "")
MEMORY_REGION = os.getenv("AGENTCORE_REGION", os.getenv("BEDROCK_REGION", "us-west-2"))
_client = None


def _get_client():
    global _client
    if _client is None and MEMORY_ID:
        import boto3
        _client = boto3.client("bedrock-agentcore", region_name=MEMORY_REGION)
    return _client


def store_conversation(actor_id: str, session_id: str, user_text: str, assistant_text: str) -> None:
    """Store a user/assistant exchange as a memory event."""
    client = _get_client()
    if not client or not MEMORY_ID:
        return
    try:
        client.create_event(
            memoryId=MEMORY_ID,
            actorId=actor_id or "default",
            sessionId=session_id,
            eventTimestamp=datetime.now(),
            payload=[
                {"conversational": {"content": {"text": user_text}, "role": "USER"}},
                {"conversational": {"content": {"text": assistant_text[:4000]}, "role": "ASSISTANT"}},
            ],
        )
        logger.info(f"Memory event stored for actor={actor_id} session={session_id}")
    except Exception as e:
        logger.warning(f"Failed to store memory event: {e}")


def retrieve_context(actor_id: str, query: str, max_results: int = 5) -> str:
    """Retrieve relevant memories for an actor to inject as context."""
    client = _get_client()
    if not client or not MEMORY_ID:
        return ""
    context_parts = []
    for namespace in [f"/facts/{actor_id}/", f"/summaries/{actor_id}/"]:
        try:
            resp = client.retrieve_memories(
                memoryId=MEMORY_ID,
                namespace=namespace,
                query=query,
                maxResults=max_results,
            )
            for record in resp.get("memoryRecords", []):
                content = record.get("content", {}).get("text", "")
                if content:
                    context_parts.append(content)
        except Exception as e:
            logger.debug(f"Memory retrieve from {namespace}: {e}")
    if not context_parts:
        return ""
    return "\n\nRELEVANT MEMORY CONTEXT:\n" + "\n---\n".join(context_parts[:max_results])
