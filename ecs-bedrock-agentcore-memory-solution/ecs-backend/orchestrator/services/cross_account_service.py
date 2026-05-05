"""Cross-account onboarding service: CFN link generation, trust policy management, access verification."""
import json
import os
import logging
import re
from urllib.parse import quote_plus

import boto3

logger = logging.getLogger(__name__)

OPERATOR_ACCOUNT = os.getenv("AWS_ACCOUNT_ID", "256358067059")
STACK_NAME = os.getenv("STACK_NAME", "sandbox-longrun-0426")
MCP_ROLE_NAME = os.getenv("MCP_ROLE_NAME", f"{STACK_NAME}-McpAssumeRole")
EXTERNAL_ID = os.getenv("CROSS_ACCOUNT_EXTERNAL_ID", "openab-scan")
CFN_TEMPLATE_URL = os.getenv("CFN_TEMPLATE_URL", "")
ONBOARD_TABLE = os.getenv("ONBOARD_TABLE", f"{STACK_NAME}-cross-account-state")
REGION = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "us-west-2"))

TARGET_ROLE_NAME = "OpenAB-ReadOnlyAccess"
_ACCOUNT_RE = re.compile(r"^\d{12}$")


def _iam():
    return boto3.client("iam", region_name=REGION)


def _sts():
    return boto3.client("sts", region_name=REGION)


def _ddb():
    return boto3.resource("dynamodb", region_name=REGION).Table(ONBOARD_TABLE)


def _target_role_arn(account_id: str) -> str:
    return f"arn:aws:iam::{account_id}:role/{TARGET_ROLE_NAME}"


def is_valid_account(account_id: str) -> bool:
    return bool(_ACCOUNT_RE.match(account_id))


def generate_cfn_link(account_id: str) -> str:
    """Generate CloudFormation Quick-Create URL for the target account."""
    template_url = CFN_TEMPLATE_URL
    if not template_url:
        template_url = f"https://{STACK_NAME}-source-{OPERATOR_ACCOUNT}-{REGION}.s3.{REGION}.amazonaws.com/templates/cross-account-readonly-role.yaml"

    params = (
        f"stackName=OpenAB-ReadOnlyAccess"
        f"&templateURL={quote_plus(template_url)}"
        f"&param_TrustedAccountId={OPERATOR_ACCOUNT}"
        f"&param_TrustedRoleName={MCP_ROLE_NAME}"
        f"&param_ExternalId={EXTERNAL_ID}"
    )
    return f"https://{REGION}.console.aws.amazon.com/cloudformation/home?region={REGION}#/stacks/quickcreate?{params}"


def is_onboarded(account_id: str) -> bool:
    """Check if account has completed onboarding."""
    try:
        resp = _ddb().get_item(Key={"account_id": account_id})
        return resp.get("Item", {}).get("status") == "active"
    except Exception as e:
        logger.warning(f"DDB check failed: {e}")
        return False


def update_trust_policy(account_id: str) -> bool:
    """Add target account role ARN to the MCP role's inline policy."""
    iam = _iam()
    policy_name = "AssumeTargetRoles"
    target_arn = _target_role_arn(account_id)

    try:
        resp = iam.get_role_policy(RoleName=MCP_ROLE_NAME, PolicyName=policy_name)
        doc = resp["PolicyDocument"]
    except iam.exceptions.NoSuchEntityException:
        doc = {"Version": "2012-10-17", "Statement": [{"Effect": "Allow", "Action": "sts:AssumeRole", "Resource": [], "Condition": {"StringEquals": {"sts:ExternalId": EXTERNAL_ID}}}]}

    stmt = doc["Statement"][0]
    resources = stmt.get("Resource", [])
    if isinstance(resources, str):
        resources = [resources]
    if target_arn not in resources:
        resources.append(target_arn)
    stmt["Resource"] = resources

    iam.put_role_policy(RoleName=MCP_ROLE_NAME, PolicyName=policy_name, PolicyDocument=json.dumps(doc))
    logger.info(f"Trust policy updated: added {target_arn}")
    return True


def verify_access(account_id: str) -> bool:
    """Verify we can assume the role in the target account."""
    try:
        _sts().assume_role(
            RoleArn=_target_role_arn(account_id),
            RoleSessionName="openab-verify",
            ExternalId=EXTERNAL_ID,
            DurationSeconds=900,
        )
        return True
    except Exception as e:
        logger.warning(f"verify_access failed for {account_id}: {e}")
        return False


def complete_onboarding(account_id: str) -> dict:
    """Run full onboarding: update trust, verify access, record state."""
    if not is_valid_account(account_id):
        return {"success": False, "error": "Invalid account ID"}

    try:
        update_trust_policy(account_id)
    except Exception as e:
        return {"success": False, "error": f"Trust policy update failed: {e}"}

    if not verify_access(account_id):
        return {"success": False, "error": "Cannot assume role in target account. Ensure the CFN stack was deployed."}

    import time
    _ddb().put_item(Item={"account_id": account_id, "status": "active", "role_arn": _target_role_arn(account_id), "onboarded_at": int(time.time()), "ttl": int(time.time()) + 86400 * 30})
    return {"success": True, "role_arn": _target_role_arn(account_id)}


def get_assume_role_arn(account_id: str) -> str:
    """Return the target role ARN for an onboarded account."""
    return _target_role_arn(account_id)
