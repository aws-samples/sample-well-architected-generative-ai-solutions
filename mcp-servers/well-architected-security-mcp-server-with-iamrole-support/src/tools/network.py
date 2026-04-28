# MIT No Attribution
#
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Network security tools for the MCP server."""

import os
from typing import Dict, List

from loguru import logger
from mcp.server.fastmcp import Context
from pydantic import Field

from src.util.credential_utils import create_aws_session
from src.util.network_security import check_network_security
from src.util.resource_utils import list_services_in_region

AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

# Module-level reference set by register()
_context_storage = None

FIELD_AWS_REGION = Field(
    AWS_REGION, description="AWS region to check for security services status"
)
FIELD_STORE_IN_CONTEXT_TRUE = Field(
    True, description="Whether to store results in context for access by other tools"
)
FIELD_NETWORK_SERVICES = Field(
    ["elb", "vpc", "apigateway", "cloudfront"],
    description="List of network services to check. Options: elb, vpc, apigateway, cloudfront",
)
FIELD_INCLUDE_NON_COMPLIANT_ONLY = Field(
    False, description="Whether to include only non-compliant resources in the results"
)


async def check_network_security_tool(
    ctx: Context,
    region: str = FIELD_AWS_REGION,
    services: List[str] = FIELD_NETWORK_SERVICES,
    include_non_compliant_only: bool = FIELD_INCLUDE_NON_COMPLIANT_ONLY,
    store_in_context: bool = FIELD_STORE_IN_CONTEXT_TRUE,
) -> Dict:
    """Check if AWS network resources are configured for secure data-in-transit.

    This tool identifies network resources using Resource Explorer and checks if they
    are properly configured for data protection in transit according to AWS Well-Architected
    Framework Security Pillar best practices.

    ## Response format
    Returns a dictionary with:
    - region: The region that was checked
    - resources_checked: Total number of network resources checked
    - compliant_resources: Number of resources with proper in-transit protection
    - non_compliant_resources: Number of resources without proper in-transit protection
    - compliance_by_service: Breakdown of compliance by service type
    - resource_details: Details about each resource checked
    - recommendations: Recommendations for improving data protection in transit

    ## AWS permissions required
    - resource-explorer-2:ListResources
    - Read permissions for each network service being analyzed (elb:DescribeLoadBalancers, etc.)
    """
    try:
        logger.info(f"Starting network security check for region: {region}")
        logger.info(f"Services to check: {', '.join(services)}")
        logger.info("Using enhanced AWS credentials chain (supports AssumeRole)")

        session = create_aws_session()

        results = await check_network_security(
            region, services, session, ctx, include_non_compliant_only
        )

        if store_in_context:
            context_key = f"network_security_{region}"
            _context_storage[context_key] = results
        return results

    except Exception as e:
        logger.error(f"Error checking network security: {e}")
        return {
            "region": region,
            "services_checked": services,
            "error": str(e),
            "message": "Error checking network security status.",
        }


async def list_services_in_region_tool(
    ctx: Context,
    region: str = FIELD_AWS_REGION,
    store_in_context: bool = FIELD_STORE_IN_CONTEXT_TRUE,
) -> Dict:
    """List all AWS services being used in a specific region.

    This tool identifies which AWS services are actively being used in the specified region
    by discovering resources through AWS Resource Explorer or direct API calls.

    ## Response format
    Returns a dictionary with:
    - region: The region that was checked
    - services: List of AWS services being used in the region
    - service_counts: Dictionary mapping service names to resource counts
    - total_resources: Total number of resources found across all services

    ## AWS permissions required
    - resource-explorer-2:Search (if Resource Explorer is set up)
    - Read permissions for various AWS services
    """
    logger.info(f"Starting service discovery for region: {region}")
    logger.info("Using enhanced AWS credentials chain (supports AssumeRole)")

    session = create_aws_session()

    results = {"region": region, "services": [], "service_counts": {}, "total_resources": 0}

    try:
        logger.info(f"Attempting to discover services using Resource Explorer in {region}...")
        results = await list_services_in_region(region, session, ctx)

    except Exception as e:
        logger.error(f"Resource Explorer method failed: {e}")
        logger.info("Falling back to alternative service discovery method...")

        return {
            "region": region,
            "error": f"Discovery methods failed. Primary error: {str(e)}.",
            "message": f"Error listing services in region {region}.",
            "services": [],
            "service_counts": {},
            "total_resources": 0,
        }

    if store_in_context:
        context_key = f"services_in_region_{region}"
        _context_storage[context_key] = results
    return results


def register(mcp, context_storage):
    """Register network tools with the MCP server."""
    global _context_storage
    _context_storage = context_storage

    mcp.tool(name="CheckNetworkSecurity")(check_network_security_tool)
    mcp.tool(name="ListServicesInRegion")(list_services_in_region_tool)
