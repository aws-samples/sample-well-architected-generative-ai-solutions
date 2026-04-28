# MIT No Attribution
#
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Security service tools for the MCP server."""

import datetime
import os
from typing import Dict, List, Optional

from loguru import logger
from mcp.server.fastmcp import Context
from pydantic import Field

from src.util.credential_utils import (
    create_aws_session,
    get_session_info,
    validate_assume_role_config,
)
from src.util.security_services import (
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

AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

# Module-level reference set by register()
_context_storage = None

FIELD_AWS_REGION = Field(
    AWS_REGION, description="AWS region to check for security services status"
)
FIELD_STORE_IN_CONTEXT_TRUE = Field(
    True, description="Whether to store results in context for access by other tools"
)
FIELD_DEBUG_TRUE = Field(
    True, description="Whether to include detailed debug information in the response"
)
FIELD_SECURITY_SERVICES = Field(
    ["guardduty", "inspector", "accessanalyzer", "securityhub", "trustedadvisor", "macie"],
    description="List of security services to check. Options: guardduty, inspector, accessanalyzer, securityhub, trustedadvisor, macie",
)
FIELD_ACCOUNT_ID = Field(
    None, description="Optional AWS account ID (defaults to caller's account)"
)
FIELD_MAX_FINDINGS = Field(100, description="Maximum number of findings to retrieve")
FIELD_SEVERITY_FILTER = Field(
    None,
    description="Optional severity filter (e.g., 'HIGH', 'CRITICAL', or for Trusted Advisor: 'ERROR', 'WARNING')",
)
FIELD_CHECK_ENABLED = Field(
    True, description="Whether to check if service is enabled before retrieving findings"
)
FIELD_DETAILED_FALSE = Field(
    False, description="Whether to return the full details of the stored security services data"
)


async def check_security_services(
    ctx: Context,
    region: str = FIELD_AWS_REGION,
    services: List[str] = FIELD_SECURITY_SERVICES,
    account_id: Optional[str] = FIELD_ACCOUNT_ID,
    store_in_context: bool = FIELD_STORE_IN_CONTEXT_TRUE,
    debug: bool = FIELD_DEBUG_TRUE,
) -> Dict:
    """Verify if selected AWS security services are enabled in the specified region and account.

    This consolidated tool checks the status of multiple AWS security services in a single call,
    providing a comprehensive overview of your security posture.

    ## Response format
    Returns a dictionary with:
    - region: The region that was checked
    - services_checked: List of services that were checked
    - all_enabled: Boolean indicating if all specified services are enabled
    - service_statuses: Dictionary with detailed status for each service
    - summary: Summary of security recommendations

    ## AWS permissions required
    The AgentCore Runtime IAM role must have the following permissions:
    - guardduty:ListDetectors, guardduty:GetDetector (if checking GuardDuty)
    - inspector2:GetStatus (if checking Inspector)
    - accessanalyzer:ListAnalyzers (if checking Access Analyzer)
    - securityhub:DescribeHub (if checking Security Hub)
    - support:DescribeTrustedAdvisorChecks (if checking Trusted Advisor)
    """
    try:
        start_time = datetime.datetime.now()

        if debug:
            logger.debug(f"Starting security services check for region: {region}")
            logger.debug(f"Services to check: {', '.join(services)}")

            assume_role_config = validate_assume_role_config()
            logger.debug(f"Credential config: {assume_role_config['message']}")

        session = create_aws_session()

        if debug:
            session_info = get_session_info(session)
            logger.debug(f"Session info: Account={session_info.get('account_id', 'Unknown')}, ARN={session_info.get('arn', 'Unknown')}")

        results = {
            "region": region,
            "services_checked": services,
            "all_enabled": True,
            "service_statuses": {},
        }

        if debug:
            results["debug_info"] = {
                "start_time": start_time.isoformat(),
                "credentials_source": "default_chain",
                "service_details": {},
            }

        for service_name in services:
            service_start_time = datetime.datetime.now()
            logger.info(f"Checking {service_name} status in {region}...")

            service_result = None

            if service_name.lower() == "guardduty":
                service_result = await check_guard_duty(region, session, ctx)
            elif service_name.lower() == "inspector":
                service_result = await check_inspector(region, session, ctx)
            elif service_name.lower() == "accessanalyzer":
                service_result = await check_access_analyzer(region, session, ctx)
            elif service_name.lower() == "securityhub":
                service_result = await check_security_hub(region, session, ctx)
            elif service_name.lower() == "trustedadvisor":
                service_result = await check_trusted_advisor(region, session, ctx)
            elif service_name.lower() == "macie":
                service_result = await check_macie(region, session, ctx)
            else:
                logger.warning(f"Unknown service: {service_name}. Skipping.")
                continue

            results["service_statuses"][service_name] = service_result

            if service_result and not service_result.get("enabled", False):
                results["all_enabled"] = False

            if debug:
                service_end_time = datetime.datetime.now()
                service_duration = (service_end_time - service_start_time).total_seconds()

                if "debug_info" in results and "service_details" in results["debug_info"]:
                    results["debug_info"]["service_details"][service_name] = {
                        "duration_seconds": service_duration,
                        "enabled": service_result.get("enabled", False)
                        if service_result
                        else False,
                        "timestamp": service_end_time.isoformat(),
                        "status": "success" if service_result else "error",
                    }

                logger.debug(f"{service_name} check completed in {service_duration:.2f} seconds")

        enabled_services = [
            name
            for name, status in results["service_statuses"].items()
            if status.get("enabled", False)
        ]
        disabled_services = [
            name
            for name, status in results["service_statuses"].items()
            if not status.get("enabled", False)
        ]

        summary = []
        if enabled_services:
            summary.append(f"Enabled services: {', '.join(enabled_services)}")
        if disabled_services:
            summary.append(f"Disabled services: {', '.join(disabled_services)}")
            summary.append("Consider enabling these services to improve your security posture.")

        results["summary"] = " ".join(summary)

        if store_in_context:
            context_key = f"security_services_{region}"
            _context_storage[context_key] = results
            logger.info(f"Stored security services results in context with key: {context_key}")

        return results

    except Exception as e:
        logger.error(f"Error checking security services: {e}")
        return {
            "region": region,
            "services_checked": services,
            "all_enabled": False,
            "error": str(e),
            "message": "Error checking security services status.",
        }


async def get_security_findings(
    ctx: Context,
    region: str = FIELD_AWS_REGION,
    service: str = Field(
        ...,
        description="Security service to retrieve findings from ('guardduty', 'securityhub', 'inspector', 'accessanalyzer', 'trustedadvisor', 'macie')",
    ),
    max_findings: int = FIELD_MAX_FINDINGS,
    severity_filter: Optional[str] = FIELD_SEVERITY_FILTER,
    check_enabled: bool = FIELD_CHECK_ENABLED,
) -> Dict:
    """Retrieve security findings from AWS security services.

    This tool provides a consolidated interface to retrieve findings from various AWS security
    services, including GuardDuty, Security Hub, Inspector, IAM Access Analyzer, and Trusted Advisor.

    It first checks if the specified security service is enabled in the region (using data from
    a previous CheckSecurityServices call) and only retrieves findings if the service is enabled.

    ## Response format
    Returns a dictionary with:
    - service: The security service findings were retrieved from
    - enabled: Whether the service is enabled in the specified region
    - findings: List of findings from the service (if service is enabled)
    - summary: Summary statistics about the findings (if service is enabled)
    - message: Status message or error information

    ## AWS permissions required
    - Read permissions for the specified security service

    ## Note
    For optimal performance, run CheckSecurityServices with store_in_context=True
    before using this tool. Otherwise, it will need to check if the service is enabled first.
    """
    try:
        service_name = service.lower()

        if service_name not in [
            "guardduty",
            "securityhub",
            "inspector",
            "accessanalyzer",
            "trustedadvisor",
            "macie",
        ]:
            raise ValueError(
                f"Unsupported security service: {service}. "
                + "Supported services are: guardduty, securityhub, inspector, accessanalyzer, trustedadvisor, macie"
            )

        context_key = f"security_services_{region}"
        service_status = None

        if check_enabled:
            if context_key in _context_storage:
                logger.info(f"Using stored security services data for region: {region}")
                security_data = _context_storage[context_key]

                service_statuses = security_data.get("service_statuses", {})
                if service_name in service_statuses:
                    service_status = service_statuses[service_name]

                    if not service_status.get("enabled", False):
                        return {
                            "service": service_name,
                            "enabled": False,
                            "message": f"{service_name} is not enabled in region {region}. Please enable it before retrieving findings.",
                            "setup_instructions": service_status.get(
                                "setup_instructions", "No setup instructions available."
                            ),
                        }
                else:
                    logger.info(
                        f"Service {service_name} not found in stored security services data. Will check directly."
                    )
            else:
                logger.info(
                    f"No stored security services data found for region: {region}. Will check service status directly."
                )

        session = create_aws_session()

        filter_criteria = None
        if severity_filter:
            if service_name == "guardduty":
                severity_mapping = {
                    "LOW": ["1", "2", "3"],
                    "MEDIUM": ["4", "5", "6"],
                    "HIGH": ["7", "8"],
                    "CRITICAL": ["8"],
                }
                if severity_filter.upper() in severity_mapping:
                    filter_criteria = {
                        "Criterion": {
                            "severity": {"Eq": severity_mapping[severity_filter.upper()]}
                        }
                    }
            elif service_name == "securityhub":
                filter_criteria = {
                    "SeverityLabel": [{"Comparison": "EQUALS", "Value": severity_filter.upper()}]
                }
            elif service_name == "inspector":
                filter_criteria = {
                    "severities": [{"comparison": "EQUALS", "value": severity_filter.upper()}]
                }
            elif service_name == "trustedadvisor":
                status_filter = [severity_filter.lower()]

        result = {
            "service": service_name,
            "enabled": False,
            "message": f"Error retrieving {service_name} findings",
            "findings": [],
        }

        if service_name == "guardduty":
            logger.info(f"Retrieving GuardDuty findings from {region}...")
            result = await get_guardduty_findings(
                region, session, ctx, max_findings, filter_criteria
            )
        elif service_name == "securityhub":
            logger.info(f"Retrieving Security Hub findings from {region}...")
            result = await get_securityhub_findings(
                region, session, ctx, max_findings, filter_criteria
            )
        elif service_name == "inspector":
            logger.info(f"Retrieving Inspector findings from {region}...")
            result = await get_inspector_findings(
                region, session, ctx, max_findings, filter_criteria
            )
        elif service_name == "accessanalyzer":
            logger.info(f"Retrieving IAM Access Analyzer findings from {region}...")
            result = await get_access_analyzer_findings(region, session, ctx)
        elif service_name == "trustedadvisor":
            logger.info("Retrieving Trusted Advisor security checks with Error/Warning status...")
            if severity_filter:
                status_filter = [severity_filter.lower()]
                logger.info(f"Filtering Trusted Advisor checks by status: {status_filter}")
            else:
                status_filter = ["error", "warning"]
                logger.info(f"Using default status filter for Trusted Advisor: {status_filter}")
            result = await get_trusted_advisor_findings(
                region,
                session,
                ctx,
                max_findings=max_findings,
                status_filter=status_filter,
                category_filter="security",
            )
        elif service_name == "macie":
            logger.info(f"Retrieving Macie findings from {region}...")
            result = await get_macie_findings(region, session, ctx, max_findings, filter_criteria)

        result["service"] = service_name

        if not result.get("enabled", True) and context_key in _context_storage:
            security_data = _context_storage[context_key]
            service_statuses = security_data.get("service_statuses", {})
            if service_name not in service_statuses:
                service_statuses[service_name] = {"enabled": False}
                logger.info(f"Updated context with status for {service_name}: not enabled")

        return result

    except Exception as e:
        logger.error(f"Error retrieving {service} findings: {e}")
        raise e


async def get_stored_security_context(
    ctx: Context,
    region: str = FIELD_AWS_REGION,
    detailed: bool = FIELD_DETAILED_FALSE,
) -> Dict:
    """Retrieve security services data that was stored in context from a previous CheckSecurityServices call.

    This tool allows you to access security service status data stored by the CheckSecurityServices tool
    without making additional AWS API calls. This is useful for workflows where you need to reference
    the security services status in subsequent steps.

    ## Response format
    Returns a dictionary with:
    - region: The region the data was stored for
    - available: Boolean indicating if data is available for the requested region
    - data: The stored security services data (if available and detailed=True)
    - summary: A summary of the stored data (if available)
    - timestamp: When the data was stored (if available)

    ## Note
    This tool requires that CheckSecurityServices was previously called with store_in_context=True
    for the requested region.
    """
    context_key = f"security_services_{region}"

    if context_key not in _context_storage:
        logger.info(f"No stored security services data found for region: {region}")
        return {
            "region": region,
            "available": False,
            "message": f"No security services data has been stored for region {region}. Call CheckSecurityServices with store_in_context=True first.",
        }

    stored_data = _context_storage[context_key]

    response = {
        "region": region,
        "available": True,
        "summary": stored_data.get("summary", "No summary available"),
        "all_enabled": stored_data.get("all_enabled", False),
        "services_checked": stored_data.get("services_checked", []),
    }

    if detailed:
        response["data"] = stored_data

    logger.info(f"Retrieved stored security services data for region: {region}")
    return response


async def validate_credential_configuration(
    ctx: Context,
) -> Dict:
    """Validate AWS credential configuration including AssumeRole setup.

    This tool checks the current AWS credential configuration and validates
    any AssumeRole settings from environment variables. It's useful for
    troubleshooting authentication issues and verifying cross-account access setup.

    ## Response format
    Returns a dictionary with:
    - credential_source: How credentials are being obtained
    - assume_role_configured: Whether AssumeRole is configured
    - validation_status: Whether the configuration is valid
    - session_info: Information about the current AWS session
    - recommendations: Suggestions for improving the configuration

    ## Environment Variables for AssumeRole
    - AWS_ASSUME_ROLE_ARN: The ARN of the role to assume (required for AssumeRole)
    - AWS_ASSUME_ROLE_SESSION_NAME: Session name (optional, defaults to 'mcp-server-session')
    - AWS_ASSUME_ROLE_EXTERNAL_ID: External ID for enhanced security (optional)
    """
    try:
        logger.info("Validating AWS credential configuration...")

        assume_role_config = validate_assume_role_config()

        session = create_aws_session()
        session_info = get_session_info(session)

        credential_source = "assume_role" if assume_role_config["configured"] else "default_chain"

        recommendations = []

        if assume_role_config["configured"]:
            if assume_role_config["valid"]:
                recommendations.append("AssumeRole configuration is properly set up")
                if not assume_role_config.get("external_id_configured", False):
                    recommendations.append("Consider using AWS_ASSUME_ROLE_EXTERNAL_ID for enhanced security")
            else:
                recommendations.extend([f"Fix configuration issue: {issue}" for issue in assume_role_config.get("issues", [])])
        else:
            recommendations.append("Using default AWS credentials chain - consider AssumeRole for cross-account access")

        if session_info.get("error"):
            recommendations.append("Credential validation failed - check your AWS configuration")

        return {
            "credential_source": credential_source,
            "assume_role_configured": assume_role_config["configured"],
            "validation_status": "valid" if assume_role_config["valid"] and not session_info.get("error") else "invalid",
            "assume_role_config": assume_role_config,
            "session_info": session_info,
            "recommendations": recommendations,
            "message": "Credential configuration validated successfully" if not session_info.get("error") else "Credential validation encountered issues",
        }

    except Exception as e:
        logger.error(f"Error validating credential configuration: {e}")
        return {
            "credential_source": "unknown",
            "assume_role_configured": False,
            "validation_status": "error",
            "error": str(e),
            "message": "Failed to validate credential configuration",
            "recommendations": ["Check AWS credentials and network connectivity"],
        }


def register(mcp, context_storage):
    """Register security tools with the MCP server."""
    global _context_storage
    _context_storage = context_storage

    mcp.tool(name="CheckSecurityServices")(check_security_services)
    mcp.tool(name="GetSecurityFindings")(get_security_findings)
    mcp.tool(name="GetStoredSecurityContext")(get_stored_security_context)
    mcp.tool(name="ValidateCredentialConfiguration")(validate_credential_configuration)
