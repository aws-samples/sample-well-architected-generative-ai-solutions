"""DynamoDB task memory — persist task records per user."""
import os
import time
import logging
from typing import Optional

import boto3
from boto3.dynamodb.conditions import Key

logger = logging.getLogger(__name__)

TABLE_NAME = os.getenv("TASK_TABLE_NAME", "")
TTL_DAYS = 7
_table = None


def _get_table():
    global _table
    if _table is None and TABLE_NAME:
        _table = boto3.resource("dynamodb").Table(TABLE_NAME)
    return _table


def save_task(user: str, task: dict) -> None:
    """Write or update a task record in DynamoDB."""
    table = _get_table()
    if not table:
        return
    try:
        item = {
            "user": user or "default",
            "task_id": task["id"],
            "tool": task.get("tool", ""),
            "status": task.get("status", "running"),
            "input": task.get("input", ""),
            "started": task.get("started", ""),
            "completed": task.get("completed", ""),
            "brief": task.get("brief", "")[:4000],
            "error": task.get("error", ""),
            "origin": task.get("origin", ""),
            "branch": task.get("branch", ""),
            "commit": task.get("commit", ""),
            "ttl": int(time.time()) + TTL_DAYS * 86400,
        }
        table.put_item(Item={k: v for k, v in item.items() if v != ""})
    except Exception as e:
        logger.warning(f"Failed to save task to DynamoDB: {e}")


def get_recent_tasks(user: str = "default", limit: int = 50) -> list[dict]:
    """Query recent tasks for a user, newest first."""
    table = _get_table()
    if not table:
        return []
    try:
        resp = table.query(
            KeyConditionExpression=Key("user").eq(user or "default"),
            ScanIndexForward=False,
            Limit=limit,
        )
        return resp.get("Items", [])
    except Exception as e:
        logger.warning(f"Failed to query tasks: {e}")
        return []


def get_task(user: str, task_id: str) -> Optional[dict]:
    """Get a single task record."""
    table = _get_table()
    if not table:
        return None
    try:
        resp = table.get_item(Key={"user": user or "default", "task_id": task_id})
        return resp.get("Item")
    except Exception as e:
        logger.warning(f"Failed to get task: {e}")
        return None
