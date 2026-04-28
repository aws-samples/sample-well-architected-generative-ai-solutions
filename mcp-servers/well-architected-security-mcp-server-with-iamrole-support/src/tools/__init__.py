# MIT No Attribution
#
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Tool registration modules for the MCP server."""

from src.tools.security import register as register_security_tools
from src.tools.storage import register as register_storage_tools
from src.tools.network import register as register_network_tools


def register_all(mcp, context_storage):
    """Register all tool modules with the MCP server."""
    register_security_tools(mcp, context_storage)
    register_storage_tools(mcp, context_storage)
    register_network_tools(mcp, context_storage)
