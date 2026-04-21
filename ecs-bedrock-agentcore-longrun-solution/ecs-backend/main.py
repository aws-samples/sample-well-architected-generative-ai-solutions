"""
AgentCore Long-Running Orchestrator Backend
FastAPI application with WebSocket support for async task dispatch via Bedrock AgentCore Runtime.
"""
import os
import sys
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def create_app():
    """Create the FastAPI application."""
    from orchestrator.app import create_orchestrator_app
    return create_orchestrator_app()


try:
    app = create_app()
    logger.info("AgentCore Long-Running Orchestrator started successfully")
except Exception as e:
    logger.error(f"Failed to initialize: {e}")
    from fastapi import FastAPI
    app = FastAPI(title="Orchestrator - Init Failed")

    @app.get("/health")
    async def health():
        return {"status": "unhealthy", "error": str(e)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
