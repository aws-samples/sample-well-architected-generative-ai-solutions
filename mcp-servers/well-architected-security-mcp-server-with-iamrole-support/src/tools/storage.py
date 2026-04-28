# MIT No Attribution
#
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Storage security tools for the MCP server."""

import os
from typing import Dict, List

from loguru import logger
from mcp.server.fastmcp import Context
from pydantic import Field

from src.util.credential_utils import create_aws_session
from src.util.storage_security import check_storage_encryption

AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

# Module-level reference set by register()
_context_storage = None

FIELD_AWS_REGION = Field(
    AWS_REGION, description="AWS region to check for security services status"
)
FIELD_STORE_IN_CONTEXT_TRUE = Field(
    True, description="Whether to store results in context for access by other tools"
)
FIELD_STORAGE_SERVICES = Field(
    ["s3", "ebs", "rds", "dynamodb", "efs", "elasticache"],
    description="List of storage services to check. Options: s3, ebs, rds, dynamodb, efs, elasticache",
)
FIELD_INCLUDE_UNENCRYPTED_ONLY = Field(
    False, description="Whether to include only unencrypted resources in the results"
)


async def check_storage_encryption_tool(
    ctx: Context,
    region: str = FIELD_AWS_REGION,
    services: List[str] = FIELD_STORAGE_SERVICES,
    include_unencrypted_only: bool = FIELD_INCLUDE_UNENCRYPTED_ONLY,
    store_in_context: bool = FIELD_STORE_IN_CONTEXT_TRUE,
) -> Dict:
    """Check if AWS storage resources have encryption enabled.

    This tool identifies storage resources using Resource Explorer and checks if they
    are properly configured for data protection at rest according to AWS Well-Architected
    Framework Security Pillar best practices.

    ## Response format
    Returns a dictionary with:
    - region: The region that was checked
    - resources_checked: Total number of storage resources checked
    - compliant_resources: Number of resources with proper encryption
    - non_compliant_resources: Number of resources without proper encryption
    - compliance_by_service: Breakdown of compliance by service type
    - resource_details: Details about each resource checked
    - recommendations: Recommendations for improving data protection at rest

    ## AWS permissions required
    - resource-explorer-2:ListResources
    - Read permissions for each storage service being analyzed (s3:GetEncryptionConfiguration, etc.)
    """
    try:
        logger.info(f"Starting storage encryption check for region: {region}")
        logger.info(f"Services to check: {', '.join(services)}")
        logger.info("Using enhanced AWS credentials chain (supports AssumeRole)")

        session = create_aws_session()

        results = await check_storage_encryption(
            region, services, session, ctx, include_unencrypted_only
        )

        if store_in_context:
            context_key = f"storage_encryption_{region}"
            _context_storage[context_key] = results
        return results

    except Exception as e:
        logger.error(f"Error checking storage encryption: {e}")
        return {
            "region": region,
            "services_checked": services,
            "error": str(e),
            "message": "Error checking storage encryption status.",
        }


def register(mcp, context_storage):
    """Register storage tools with the MCP server."""
    global _context_storage
    _context_storage = context_storage

    mcp.tool(name="CheckStorageEncryption")(check_storage_encryption_tool)
