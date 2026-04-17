"""Tests for services/mcp_client_service.py"""

import pytest
from services.mcp_client_service import MCPClientService


class TestMCPClientService:
    def test_init_demo_mode(self):
        svc = MCPClientService(demo_mode=True)
        assert svc.demo_mode is True

    def test_init_non_demo_mode(self):
        svc = MCPClientService(demo_mode=False)
        assert svc.demo_mode is False

    @pytest.mark.asyncio
    async def test_health_check_demo(self):
        svc = MCPClientService(demo_mode=True)
        assert await svc.health_check() == "healthy"

    @pytest.mark.asyncio
    async def test_health_check_non_demo(self):
        svc = MCPClientService(demo_mode=False)
        assert await svc.health_check() == "degraded"

    @pytest.mark.asyncio
    async def test_get_available_tools_demo(self):
        svc = MCPClientService(demo_mode=True)
        tools = await svc.get_available_tools()
        assert len(tools) == 1
        assert tools[0]["name"] == "demo_tool"

    @pytest.mark.asyncio
    async def test_get_available_tools_non_demo(self):
        svc = MCPClientService(demo_mode=False)
        tools = await svc.get_available_tools()
        assert tools == []
