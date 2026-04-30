"""AgentCore Memory service — repo-scoped conversation storage and retrieval."""
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


def store_conversation(actor_id: str, session_id: str, user_text: str, assistant_text: str,
                       repo_url: str = "", branch: str = "") -> None:
    """Store a user/assistant exchange with repo context as a memory event."""
    client = _get_client()
    if not client or not MEMORY_ID:
        return
    try:
        # Prefix user message with repo context so Memory's semantic extraction
        # associates facts with the correct repository and branch
        repo_prefix = ""
        if repo_url:
            repo_prefix = f"[repo={repo_url}"
            if branch:
                repo_prefix += f" branch={branch}"
            repo_prefix += "] "

        client.create_event(
            memoryId=MEMORY_ID,
            actorId=actor_id or "default",
            sessionId=session_id,
            eventTimestamp=datetime.now(),
            payload=[
                {"conversational": {"content": {"text": f"{repo_prefix}{user_text}"}, "role": "USER"}},
                {"conversational": {"content": {"text": assistant_text[:4000]}, "role": "ASSISTANT"}},
            ],
        )
        logger.info(f"Memory event stored for actor={actor_id} session={session_id} repo={repo_url}")
    except Exception as e:
        logger.warning(f"Failed to store memory event: {e}")


def retrieve_context(actor_id: str, query: str, repo_url: str = "", max_results: int = 5) -> str:
    """Retrieve relevant memories scoped to a repo for an actor."""
    client = _get_client()
    if not client or not MEMORY_ID:
        return ""
    # Include repo in the query so semantic search prioritizes repo-relevant facts
    scoped_query = f"repo {repo_url}: {query}" if repo_url else query
    context_parts = []
    for namespace in [f"/facts/{actor_id}/", f"/summaries/{actor_id}/"]:
        try:
            resp = client.retrieve_memories(
                memoryId=MEMORY_ID,
                namespace=namespace,
                query=scoped_query,
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
    return "\n\nPREVIOUS SESSION CONTEXT (from memory):\n" + "\n---\n".join(context_parts[:max_results])
