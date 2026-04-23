"""
Cloud Optimization Assistant (COA) Backend - AgentCore Runtime
Entry point for the FastAPI application using Bedrock AgentCore Runtime.
"""

import os
import sys
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AppInitializationError(Exception):
    """Exception raised when app initialization fails"""
    pass


def check_agentcore_availability() -> dict:
    """Check if AgentCore services are available via SSM parameters."""
    result = {
        "available": False,
        "param_prefix": os.getenv("PARAM_PREFIX", "coa"),
        "region": os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
        "parameters_found": 0,
        "error": None,
    }
    try:
        import boto3
        ssm = boto3.client("ssm", region_name=result["region"])
        resp = ssm.get_parameters_by_path(
            Path=f"/{result['param_prefix']}/agentcore/", MaxResults=10
        )
        result["parameters_found"] = len(resp.get("Parameters", []))
        result["available"] = result["parameters_found"] > 0
    except Exception as e:
        result["error"] = str(e)
        logger.warning(f"AgentCore availability check failed: {e}")
    return result


def create_app():
    """Create the AgentCore FastAPI application with fallback to minimal mode."""
    try:
        force_real = os.getenv("FORCE_REAL_AGENTCORE", "false").lower() == "true"
        availability = check_agentcore_availability()

        if force_real or availability["available"]:
            from agentcore.app import create_agentcore_app
            app = create_agentcore_app()
            logger.info("AgentCore backend initialized with full agent support")
            return app

        from agentcore.app import create_agentcore_app_minimal
        app = create_agentcore_app_minimal()
        logger.info("AgentCore backend initialized in minimal mode")
        return app

    except Exception as e:
        logger.warning(f"Full AgentCore init failed: {e}, trying minimal mode")
        try:
            from agentcore.app import create_agentcore_app_minimal
            app = create_agentcore_app_minimal()
            logger.info("AgentCore backend initialized in minimal mode (fallback)")
            return app
        except Exception as fallback_err:
            raise AppInitializationError(
                f"AgentCore initialization failed: {fallback_err}"
            )


def log_startup_info():
    """Log startup information."""
    logger.info("=== COA Backend Startup ===")
    logger.info(f"mode: agentcore")
    logger.info(f"python: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    logger.info(f"region: {os.getenv('AWS_DEFAULT_REGION', 'us-east-1')}")
    logger.info(f"param_prefix: {os.getenv('PARAM_PREFIX', 'coa')}")
    logger.info(f"environment: {os.getenv('ENVIRONMENT', 'development')}")
    logger.info("===========================")


# Application initialization
try:
    log_startup_info()
    app = create_app()
    logger.info("COA Backend started successfully")
except Exception as e:
    logger.error(f"Failed to initialize COA Backend: {e}")
    from fastapi import FastAPI, HTTPException

    app = FastAPI(title="COA Backend - Initialization Failed")

    @app.get("/health")
    async def health_check():
        return {"status": "unhealthy", "error": "initialization_failed", "timestamp": datetime.utcnow().isoformat()}

    @app.get("/")
    async def root():
        raise HTTPException(status_code=503, detail="Backend initialization failed")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=os.getenv("HOST", "0.0.0.0"), port=int(os.getenv("PORT", 8000)))
