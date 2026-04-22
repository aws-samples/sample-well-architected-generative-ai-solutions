"""Tests for main.py - AgentCore application entry point."""

import pytest
from unittest.mock import patch, MagicMock


class TestCheckAgentcoreAvailability:
    def test_available_when_parameters_found(self, monkeypatch):
        monkeypatch.setenv("PARAM_PREFIX", "coa")
        monkeypatch.setenv("AWS_DEFAULT_REGION", "us-west-2")
        with patch("boto3.client") as mock_client:
            ssm = MagicMock()
            ssm.get_parameters_by_path.return_value = {"Parameters": [{"Name": "/coa/agentcore/test"}]}
            mock_client.return_value = ssm
            from main import check_agentcore_availability
            result = check_agentcore_availability()
            assert result["available"] is True
            assert result["parameters_found"] == 1

    def test_not_available_when_no_parameters(self, monkeypatch):
        monkeypatch.setenv("PARAM_PREFIX", "coa")
        with patch("boto3.client") as mock_client:
            ssm = MagicMock()
            ssm.get_parameters_by_path.return_value = {"Parameters": []}
            mock_client.return_value = ssm
            from main import check_agentcore_availability
            result = check_agentcore_availability()
            assert result["available"] is False

    def test_handles_exception(self, monkeypatch):
        with patch("boto3.client", side_effect=Exception("no creds")):
            from main import check_agentcore_availability
            result = check_agentcore_availability()
            assert result["available"] is False
            assert result["error"] is not None

    def test_defaults(self):
        from main import check_agentcore_availability
        with patch("boto3.client", side_effect=Exception("test")):
            result = check_agentcore_availability()
            assert result["param_prefix"] == "coa"
            assert result["region"] == "us-east-1"


class TestCreateApp:
    def test_creates_full_app_when_available(self, monkeypatch):
        monkeypatch.setenv("PARAM_PREFIX", "coa")
        with patch("main.check_agentcore_availability", return_value={"available": True}):
            with patch("agentcore.app.create_agentcore_app") as mock_create:
                mock_create.return_value = MagicMock()
                from main import create_app
                app = create_app()
                mock_create.assert_called_once()

    def test_creates_minimal_app_when_not_available(self, monkeypatch):
        with patch("main.check_agentcore_availability", return_value={"available": False}):
            with patch("agentcore.app.create_agentcore_app_minimal") as mock_minimal:
                mock_minimal.return_value = MagicMock()
                from main import create_app
                app = create_app()
                mock_minimal.assert_called_once()

    def test_force_real_agentcore(self, monkeypatch):
        monkeypatch.setenv("FORCE_REAL_AGENTCORE", "true")
        with patch("agentcore.app.create_agentcore_app") as mock_create:
            mock_create.return_value = MagicMock()
            from main import create_app
            app = create_app()
            mock_create.assert_called_once()

    def test_fallback_to_minimal_on_error(self):
        with patch("main.check_agentcore_availability", return_value={"available": True}):
            with patch("agentcore.app.create_agentcore_app", side_effect=Exception("fail")):
                with patch("agentcore.app.create_agentcore_app_minimal") as mock_minimal:
                    mock_minimal.return_value = MagicMock()
                    from main import create_app
                    app = create_app()
                    mock_minimal.assert_called_once()

    def test_raises_when_all_fail(self):
        with patch("main.check_agentcore_availability", return_value={"available": True}):
            with patch("agentcore.app.create_agentcore_app", side_effect=Exception("fail")):
                with patch("agentcore.app.create_agentcore_app_minimal", side_effect=Exception("also fail")):
                    from main import create_app, AppInitializationError
                    with pytest.raises(AppInitializationError):
                        create_app()


class TestLogStartupInfo:
    def test_logs_without_error(self, monkeypatch):
        monkeypatch.setenv("AWS_DEFAULT_REGION", "us-west-2")
        monkeypatch.setenv("PARAM_PREFIX", "test")
        monkeypatch.setenv("ENVIRONMENT", "dev")
        from main import log_startup_info
        log_startup_info()  # Should not raise
