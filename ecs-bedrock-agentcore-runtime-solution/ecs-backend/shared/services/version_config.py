"""
Backend version configuration service for AgentCore runtime.
"""

import os
import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class VersionConfigService:
    """Service for managing backend version configuration."""

    def __init__(self):
        self.version_info = {
            "version": "agentcore",
            "detected_at": datetime.utcnow().isoformat(),
            "param_prefix": os.getenv("PARAM_PREFIX", "coa"),
            "aws_region": os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
        }

    def get_version_config(self) -> Dict[str, Any]:
        """Get AgentCore configuration."""
        return {
            "version": "agentcore",
            "features": {
                "strands_agents": True,
                "agentcore_runtime": True,
            },
            "services": {
                "strands_discovery": True,
                "agentcore_invocation": True,
            },
            "fallback_mode": True,
            "graceful_degradation": True,
        }

    def validate_version_constraints(self) -> Dict[str, Any]:
        """Validate AgentCore constraints."""
        warnings = []
        recommendations = []

        if not os.getenv("PARAM_PREFIX"):
            warnings.append("PARAM_PREFIX not set, using default 'coa'")
            recommendations.append("Set PARAM_PREFIX for proper AgentCore configuration")
        if not os.getenv("AWS_DEFAULT_REGION"):
            warnings.append("AWS_DEFAULT_REGION not set, using default 'us-east-1'")

        return {
            "valid": True,
            "version": "agentcore",
            "errors": [],
            "warnings": warnings,
            "recommendations": recommendations,
        }

    def get_version_summary(self) -> Dict[str, Any]:
        """Get a summary of version configuration and validation status."""
        config = self.get_version_config()
        validation = self.validate_version_constraints()
        return {
            **self.version_info,
            "config": config,
            "validation": validation,
        }

    def get_feature_flags(self) -> Dict[str, bool]:
        return self.get_version_config()["features"]

    def get_service_flags(self) -> Dict[str, bool]:
        return self.get_version_config()["services"]

    async def health_check(self) -> str:
        try:
            result = self.validate_version_constraints()
            if result["warnings"]:
                return "degraded"
            return "healthy"
        except Exception:
            return "unhealthy"


_version_config_service: Optional[VersionConfigService] = None


def get_version_config_service() -> VersionConfigService:
    global _version_config_service
    if _version_config_service is None:
        _version_config_service = VersionConfigService()
    return _version_config_service


def is_agentcore_version() -> bool:
    return True


def get_version_specific_config() -> Dict[str, Any]:
    return get_version_config_service().get_version_config()
