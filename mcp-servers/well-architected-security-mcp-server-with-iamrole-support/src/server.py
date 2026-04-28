# MIT No Attribution
#
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in
# the Software without restriction, including without limitation the rights to
# use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
# the Software, and to permit persons to whom the Software is furnished to do so.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
# FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
# COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
# IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

"""AWS Well-Architected Security Assessment Tool MCP Server"""

import argparse
import os
import sys
from typing import Dict

from loguru import logger
from mcp.server.fastmcp import FastMCP

from src import __version__
from src.consts import INSTRUCTIONS
from src.tools import register_all as register_tools
from src.prompts import register as register_prompts

# Remove default logger and add custom configuration
logger.remove()
logger.add(sys.stderr, level=os.getenv("FASTMCP_LOG_LEVEL", "DEBUG"))

# Host configuration
host = os.environ.get("MCP_HOST", "0.0.0.0")

# Initialize MCP Server with AgentCore Runtime compatibility
mcp = FastMCP(
    "well-architected-security-mcp-server",
    host=host,  # Required for AgentCore Runtime
    stateless_http=True,  # Required for AgentCore Runtime
    instructions=INSTRUCTIONS,
    dependencies=[
        "boto3",
        "requests",
        "beautifulsoup4",
        "pydantic",
        "loguru",
    ],
)

# In-memory context shared between tool calls within a single server process.
# WARNING: This is ephemeral — data is lost on restart and not shared across
# processes or stateless-HTTP requests. For persistent cross-session storage,
# back this with DynamoDB or Redis.
context_storage: Dict = {}

# Register all tools and prompts
register_tools(mcp, context_storage)
register_prompts(mcp)

# Re-export tool/prompt functions so they are importable from src.server
from src.tools.security import (  # noqa: E402
    check_security_services,
    get_security_findings,
    get_stored_security_context,
    validate_credential_configuration,
    FIELD_SEVERITY_FILTER,
)
from src.tools.storage import check_storage_encryption_tool  # noqa: E402
from src.tools.network import check_network_security_tool, list_services_in_region_tool  # noqa: E402
from src.prompts import (  # noqa: E402
    security_assessment_precheck,
    check_storage_security_prompt,
    check_network_security_prompt,
)

# Re-export utility functions so mock.patch('src.server.X') works
from src.util.security_services import (  # noqa: E402
    check_access_analyzer,
    check_guard_duty,
    check_inspector,
    check_macie,
    check_security_hub,
    check_trusted_advisor,
    get_access_analyzer_findings,
    get_guardduty_findings,
    get_inspector_findings,
    get_macie_findings,
    get_securityhub_findings,
    get_trusted_advisor_findings,
)
from src.util.network_security import check_network_security  # noqa: E402
from src.util.storage_security import check_storage_encryption  # noqa: E402
from src.util.resource_utils import list_services_in_region  # noqa: E402
from src.util.credential_utils import create_aws_session, get_session_info, validate_assume_role_config  # noqa: E402


def main():
    """Run the MCP server with CLI argument support."""
    parser = argparse.ArgumentParser(description="AWS Security Pillar MCP Server")
    parser.add_argument("--sse", action="store_true", help="Use SSE transport")
    parser.add_argument(
        "--streamable-http",
        action="store_true",
        help="Use streamable-http transport (for AgentCore Runtime)",
    )
    parser.add_argument("--port", type=int, default=8888, help="Port to run the server on")
    parser.add_argument("--host", type=str, default=None, help="Host to bind the server to (overrides MCP_HOST env var)")

    args = parser.parse_args()

    if args.host:
        mcp.settings.host = args.host

    logger.info("Starting AWS Security Pillar MCP Server")

    # Set default AWS region if not set
    if not os.environ.get("AWS_REGION"):
        os.environ["AWS_REGION"] = "us-east-1"
        logger.info("Set default AWS_REGION to us-east-1")

    # Run server with appropriate transport
    if getattr(args, "streamable_http", False):
        logger.info("Running MCP server with streamable-http transport for AgentCore Runtime")
        mcp.run(transport="streamable-http")
    elif args.sse:
        logger.info(f"Running MCP server with SSE transport on port {args.port}")
        mcp.settings.port = args.port
        mcp.run(transport="sse")
    else:
        logger.info("Running MCP server with default transport")
        mcp.run()


if __name__ == "__main__":
    main()
