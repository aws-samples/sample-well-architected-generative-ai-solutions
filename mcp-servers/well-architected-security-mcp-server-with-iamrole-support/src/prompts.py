# MIT No Attribution
#
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Prompt registration for the MCP server."""

from mcp.server.fastmcp import Context


async def security_assessment_precheck(ctx: Context) -> str:
    """Provides guidance on using CheckSecurityServices and GetSecurityFindings tools in sequence
    for a comprehensive AWS security assessment.

    This prompt explains the recommended workflow for assessing AWS security services and findings:
    1. First, check which security services are enabled using CheckSecurityServices
    2. Then, retrieve findings from the enabled services using GetSecurityFindings

    Following this sequence ensures efficient API usage and provides a structured approach to security assessment.
    """
    return """
# AWS Security Assessment Workflow Guide

This guide will help you assess your AWS security posture by checking which security services are enabled and retrieving findings from those services.

## Step 1: Check Security Services Status

First, use the `CheckSecurityServices` tool to determine which AWS security services are enabled in your account:

```python
result = await use_mcp_tool(
    server_name="well-architected-security-mcp-server",
    tool_name="CheckSecurityServices",
    arguments={
        "region": "us-east-1",  # Specify your AWS region
        "services": ["guardduty", "inspector", "accessanalyzer", "securityhub", "trustedadvisor"],
        # AWS credentials will be automatically detected from the runtime environment
        "store_in_context": True  # Important: store results for later use
    }
)
```

This will check the status of each security service and store the results in context for later use.

## Step 2: Analyze the Results

Review the results to see which services are enabled:

```python
enabled_services = []
for service, status in result['service_statuses'].items():
    if status.get('enabled', False):
        enabled_services.append(service)
        print(f"✅ {service} is enabled")
    else:
        print(f"❌ {service} is not enabled")
```

## Step 3: Retrieve Findings from Enabled Services

For each enabled service, use the `GetSecurityFindings` tool to retrieve findings:

```python
for service in enabled_services:
    findings = await use_mcp_tool(
        server_name="well-architected-security-mcp-server",
        tool_name="GetSecurityFindings",
        arguments={
            "region": "us-east-1",  # Use the same region as in Step 1
            "service": service,
            "max_findings": 100,  # Adjust as needed
            "severity_filter": "HIGH",  # Optional: filter by severity
            "check_enabled": True  # Verify service is enabled before retrieving findings
        }
    )

    # Process the findings
    if findings.get('findings'):
        print(f"Found {len(findings['findings'])} {service} findings")
        # Analyze findings here
```

## Step 4: Summarize Security Posture

After retrieving findings from all enabled services, summarize the security posture:

```python
total_findings = 0
findings_by_service = {}

for service in enabled_services:
    # Get findings count for each service
    # Implement your summary logic here
```

## Best Practices

1. Always run `CheckSecurityServices` first with `store_in_context=True`
2. Use `GetSecurityFindings` only for services that are enabled
3. Consider filtering findings by severity to focus on high-risk issues first
4. For large environments, process findings in batches

By following this workflow, you'll efficiently assess your AWS security posture and identify potential security issues.
"""


async def check_storage_security_prompt(ctx: Context) -> str:
    """Provides guidance on checking AWS storage resources for proper encryption and security configuration.

    This prompt explains the recommended workflow for assessing storage security:
    1. First, identify available storage services in the target region
    2. Then, check if these storage resources have encryption enabled
    3. Finally, analyze the results and implement recommended remediation steps

    This approach helps ensure data protection at rest according to AWS Well-Architected Framework
    Security Pillar best practices.
    """
    return """
# AWS Storage Security Assessment Guide

This guide will help you assess the security of your AWS storage resources by checking for proper encryption and security configurations.

## Step 1: Identify Available Storage Services

First, determine which storage services are available in your target region:

```python
# Option 1: List all services in the region
services_result = await use_mcp_tool(
    server_name="well-architected-security-mcp-server",
    tool_name="ListServicesInRegion",
    arguments={
        "region": "us-east-1",  # Specify your AWS region
        # AWS credentials will be automatically detected from the runtime environment
        "store_in_context": True  # Store results for later use
    }
)

# Option 2: List resource types (alternative approach)
resource_types = await use_mcp_tool(
    server_name="well-architected-security-mcp-server",
    tool_name="ListResourceTypes",
    arguments={
        "region": "us-east-1",  # Specify your AWS region
        # AWS credentials will be automatically detected from the runtime environment
        "store_in_context": True  # Store results for later use
    }
)
```

## Step 2: Filter for Storage Services

Next, filter the results to focus on storage services:

```python
# Define storage services to check
storage_services = ['s3', 'ebs', 'rds', 'dynamodb', 'efs', 'elasticache']

# Filter available services to include only storage services
available_storage_services = []

# If using ListServicesInRegion result
if 'services' in services_result:
    available_storage_services = [s for s in services_result['services'] if s in storage_services]

# If using ListResourceTypes result
if 'storage_services' in resource_types:
    available_storage_services = resource_types['storage_services']

print(f"Available storage services: {', '.join(available_storage_services)}")
```

## Step 3: Check Storage Encryption

Now, check if your storage resources have encryption enabled:

```python
encryption_result = await use_mcp_tool(
    server_name="well-architected-security-mcp-server",
    tool_name="CheckStorageEncryption",
    arguments={
        "region": "us-east-1",  # Specify your AWS region
        "services": available_storage_services,  # Use the filtered list from Step 2
        "include_unencrypted_only": False,  # Set to True to focus only on unencrypted resources
        # AWS credentials will be automatically detected from the runtime environment
        "store_in_context": True  # Store results for later use
    }
)
```

## Step 4: Analyze the Results

Review the encryption check results:

```python
# Get overall compliance statistics
total_resources = encryption_result['resources_checked']
compliant_resources = encryption_result['compliant_resources']
non_compliant_resources = encryption_result['non_compliant_resources']

print(f"Total resources checked: {total_resources}")
print(f"Compliant resources: {compliant_resources} ({(compliant_resources/total_resources)*100:.1f}% if total_resources > 0 else 0}%)")
print(f"Non-compliant resources: {non_compliant_resources} ({(non_compliant_resources/total_resources)*100:.1f}% if total_resources > 0 else 0}%)")

# Review compliance by service
for service, stats in encryption_result['compliance_by_service'].items():
    service_total = stats['resources_checked']
    service_compliant = stats['compliant_resources']
    service_non_compliant = stats['non_compliant_resources']

    if service_total > 0:
        compliance_rate = (service_compliant / service_total) * 100
        print(f"{service}: {compliance_rate:.1f}% compliant ({service_compliant}/{service_total})")
```

## Step 5: Review Non-Compliant Resources

Examine the details of non-compliant resources:

```python
# List all non-compliant resources
print("\\nNon-compliant resources:")
for resource in encryption_result['resource_details']:
    if not resource.get('compliant', True):
        print(f"- {resource['type']}: {resource['name']}")
        print(f"  Issues: {', '.join(resource['issues'])}")
        print(f"  Remediation: {', '.join(resource['remediation'])}")
```

## Step 6: Implement Recommendations

Review and implement the recommended remediation steps:

```python
print("\\nRecommendations:")
for recommendation in encryption_result['recommendations']:
    print(f"- {recommendation}")
```

## Best Practices for Storage Security

1. **Enable encryption by default** for all storage services
2. **Use customer-managed KMS keys** for sensitive data rather than AWS-managed keys
3. **Implement key rotation policies** for all customer-managed KMS keys
4. **Block public access** for S3 buckets at the account level
5. **Enable bucket key** for S3 buckets to reduce KMS API calls and costs
6. **Audit encryption settings regularly** to ensure continued compliance

By following this workflow, you'll efficiently assess your AWS storage security posture and identify resources that need encryption or security improvements.
"""


async def check_network_security_prompt(ctx: Context) -> str:
    """Provides guidance on checking AWS network resources for proper in-transit security configuration.

    This prompt explains the recommended workflow for assessing network security:
    1. First, identify available network services in the target region
    2. Then, check if these network resources have proper in-transit security measures
    3. Finally, analyze the results and implement recommended remediation steps

    This approach helps ensure data protection in transit according to AWS Well-Architected Framework
    Security Pillar best practices.
    """
    return """
# AWS Network Security Assessment Guide

This guide will help you assess the security of your AWS network resources by checking for proper in-transit security configurations.

## Step 1: Identify Available Network Services

First, determine which network services are available in your target region:

```python
# Option 1: List all services in the region
services_result = await use_mcp_tool(
    server_name="well-architected-security-mcp-server",
    tool_name="ListServicesInRegion",
    arguments={
        "region": "us-east-1",  # Specify your AWS region
        # AWS credentials will be automatically detected from the runtime environment
        "store_in_context": True  # Store results for later use
    }
)

# Option 2: List resource types (alternative approach)
resource_types = await use_mcp_tool(
    server_name="well-architected-security-mcp-server",
    tool_name="ListResourceTypes",
    arguments={
        "region": "us-east-1",  # Specify your AWS region
        # AWS credentials will be automatically detected from the runtime environment
        "store_in_context": True  # Store results for later use
    }
)
```

## Step 2: Filter for Network Services

Next, filter the results to focus on network services:

```python
# Define network services to check
network_services = ['elb', 'vpc', 'apigateway', 'cloudfront']

# Filter available services to include only network services
available_network_services = []

# If using ListServicesInRegion result
if 'services' in services_result:
    available_network_services = [s for s in services_result['services'] if s in network_services]

# If using ListResourceTypes result
if 'network_services' in resource_types:
    available_network_services = resource_types['network_services']

print(f"Available network services: {', '.join(available_network_services)}")
```

## Step 3: Check Network Security

Now, check if your network resources have proper in-transit security measures:

```python
network_result = await use_mcp_tool(
    server_name="well-architected-security-mcp-server",
    tool_name="CheckNetworkSecurity",
    arguments={
        "region": "us-east-1",  # Specify your AWS region
        "services": available_network_services,  # Use the filtered list from Step 2
        "include_non_compliant_only": False,  # Set to True to focus only on non-compliant resources
        # AWS credentials will be automatically detected from the runtime environment
        "store_in_context": True  # Store results for later use
    }
)
```

## Step 4: Analyze the Results

Review the network security check results:

```python
# Get overall compliance statistics
total_resources = network_result['resources_checked']
compliant_resources = network_result['compliant_resources']
non_compliant_resources = network_result['non_compliant_resources']

print(f"Total resources checked: {total_resources}")
print(f"Compliant resources: {compliant_resources} ({(compliant_resources/total_resources)*100:.1f}% if total_resources > 0 else 0}%)")
print(f"Non-compliant resources: {non_compliant_resources} ({(non_compliant_resources/total_resources)*100:.1f}% if total_resources > 0 else 0}%)")

# Review compliance by service
for service, stats in network_result['compliance_by_service'].items():
    service_total = stats['resources_checked']
    service_compliant = stats['compliant_resources']
    service_non_compliant = stats['non_compliant_resources']

    if service_total > 0:
        compliance_rate = (service_compliant / service_total) * 100
        print(f"{service}: {compliance_rate:.1f}% compliant ({service_compliant}/{service_total})")
```

## Step 5: Review Non-Compliant Resources

Examine the details of non-compliant resources:

```python
# List all non-compliant resources
print("\\nNon-compliant resources:")
for resource in network_result['resource_details']:
    if not resource.get('compliant', True):
        print(f"- {resource['type']}: {resource['name']}")
        print(f"  Issues: {', '.join(resource['issues'])}")
        print(f"  Remediation: {', '.join(resource['remediation'])}")
```

## Step 6: Implement Recommendations

Review and implement the recommended remediation steps:

```python
print("\\nRecommendations:")
for recommendation in network_result['recommendations']:
    print(f"- {recommendation}")
```

## Best Practices for Network Security

1. **Use HTTPS/TLS** for all public-facing endpoints
2. **Configure security policies** to use modern TLS versions (TLS 1.2 or later)
3. **Implement strict security headers** for web applications
4. **Use AWS Certificate Manager (ACM)** for managing SSL/TLS certificates
5. **Enable VPC Flow Logs** to monitor network traffic
6. **Implement network segmentation** using security groups and NACLs
7. **Use AWS WAF** to protect web applications from common exploits
8. **Regularly audit network security configurations** to ensure continued compliance

By following this workflow, you'll efficiently assess your AWS network security posture and identify resources that need security improvements for data in transit.
"""


def register(mcp):
    """Register all prompts with the MCP server."""
    mcp.prompt(name="wa-sec-check-findings")(security_assessment_precheck)
    mcp.prompt(name="wa-sec-check-storage")(check_storage_security_prompt)
    mcp.prompt(name="wa-sec-check-network")(check_network_security_prompt)
