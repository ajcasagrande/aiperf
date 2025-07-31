# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import tempfile
from pathlib import Path

import pytest
from aiperf import cli
from aiperf.common.config import ServiceConfig, UserConfig
from aiperf.common.enums import AIPerfLogLevel


@pytest.mark.integration
class TestIntegrationBasic:
    def test_mock_server_health(self, mock_server_url: str):
        """Test that the mock server is running and responding to health checks."""
        import requests

        response = requests.get(f"{mock_server_url}/health")
        assert response.status_code == 200

        health_data = response.json()
        assert "status" in health_data
        assert health_data["status"] == "healthy"

    def test_mock_server_chat_completions(self, mock_server_url: str):
        """Test direct API call to mock server chat completions endpoint."""
        import requests

        payload = {
            "model": "gpt2",
            "messages": [{"role": "user", "content": "Hello, world!"}],
            "max_tokens": 5,
            "stream": False,
        }

        response = requests.post(
            f"{mock_server_url}/v1/chat/completions",
            headers={"Content-Type": "application/json"},
            json=payload,
        )

        assert response.status_code == 200
        data = response.json()
        assert "choices" in data
        assert len(data["choices"]) > 0
        assert "message" in data["choices"][0]
        assert "content" in data["choices"][0]["message"]

    # def test_aiperf_integration_basic_non_streaming(self, user_config_for_mock_server: UserConfig, service_config_for_mock_server: ServiceConfig):
    #     """Test basic aiperf integration with mock server."""
    #     try:
    #         with tempfile.TemporaryDirectory() as output_dir:
    #             service_config = service_config_for_mock_server
    #             service_config.log_level = AIPerfLogLevel.INFO
    #             service_config.workers.min = 1
    #             service_config.workers.max = 1

    #             config = user_config_for_mock_server
    #             config.output.artifact_directory = Path(output_dir)
    #             config.loadgen.request_count = 100
    #             config.loadgen.concurrency = 100
    #             config.endpoint.streaming = True

    #             cli.profile(config, service_config)
    #     finally:
    #         # os.system("pkill -9 -f aiperf")
    #         pass

    def test_aiperf_integration_basic_streaming(
        self,
        user_config_for_mock_server: UserConfig,
        service_config_for_mock_server: ServiceConfig,
    ):
        """Test basic aiperf integration with mock server."""
        try:
            with tempfile.TemporaryDirectory() as output_dir:
                service_config = service_config_for_mock_server
                service_config.log_level = AIPerfLogLevel.INFO
                service_config.workers.min = 1
                service_config.workers.max = 20

                config = user_config_for_mock_server
                config.output.artifact_directory = Path(output_dir)
                config.loadgen.request_count = 10000
                config.loadgen.concurrency = 1000
                config.endpoint.streaming = True

                cli.profile(config, service_config)
        finally:
            # os.system("pkill -9 -f aiperf")
            pass

    # def test_aiperf_streaming_integration(self, user_config_streaming: UserConfig):
    #     """Test aiperf integration with streaming enabled."""
    #     # Create output directory
    #     with tempfile.TemporaryDirectory() as output_dir:
    #         config = user_config_streaming

    #         # Run aiperf profile command with streaming
    #         cmd = [
    #             "aiperf", "profile",
    #             "--model-names", ",".join(config.model_names),
    #             "--url", config.endpoint.url,
    #             "--endpoint-type", config.endpoint.type.value,
    #             "--output-artifact-dir", output_dir,
    #             "--request-count", "1",
    #             "--request-timeout-seconds", "10",
    #             "--streaming" if config.endpoint.streaming else "--no-streaming"
    #         ]

    #         # Set up environment to use venv
    #         env = os.environ.copy()
    #         venv_path = Path(__file__).parent.parent / ".venv"
    #         if venv_path.exists():
    #             env["PATH"] = f"{venv_path}/bin:{env['PATH']}"

    #         result = subprocess.run(
    #             cmd,
    #             capture_output=True,
    #             text=True,
    #             env=env,
    #             timeout=30
    #         )

    #         # Check that aiperf ran successfully
    #         assert result.returncode == 0, f"aiperf streaming test failed with stderr: {result.stderr}, stdout: {result.stdout}"

    #         # Check that output files were created
    #         output_files = list(Path(output_dir).glob("*.json"))
    #         assert len(output_files) > 0, "No output files generated for streaming test"
