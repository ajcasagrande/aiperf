#!/usr/bin/env python3
"""
Script to modify AIPerf config to use the local mock OpenAI API server.
This allows running AIPerf benchmarks without using real OpenAI API credits.
"""

import os
import sys
import yaml
import argparse


def modify_config(config_path, output_path=None, port=8000):
    """
    Modify the AIPerf config to use the local mock OpenAI API server.

    Args:
        config_path: Path to the original config file
        output_path: Optional path to save the modified config
        port: Port the mock server is running on (default: 8000)

    Returns:
        Path to the modified config file
    """
    # Default output path if not specified
    if output_path is None:
        base, ext = os.path.splitext(config_path)
        output_path = f"{base}_mock{ext}"

    # Read the original config
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    # Update the AI client configuration to use the mock server
    if "ai_client" in config:
        config["ai_client"]["config"] = config["ai_client"].get("config", {})
        config["ai_client"]["config"]["base_url"] = f"http://localhost:{port}"
        config["ai_client"]["config"]["api_key"] = "sk-mock-key"
    else:
        print("Warning: 'ai_client' section not found in config, creating it")
        config["ai_client"] = {
            "type": "openai",
            "config": {
                "base_url": f"http://localhost:{port}",
                "api_key": "sk-mock-key",
            },
        }

    # Save the modified config
    with open(output_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False)

    print(f"Modified config saved to: {output_path}")
    print(f"AI client now points to: http://localhost:{port}")

    return output_path


def main():
    parser = argparse.ArgumentParser(
        description="Modify AIPerf config to use local mock OpenAI API server"
    )
    parser.add_argument("config_path", help="Path to the original config file")
    parser.add_argument(
        "--output",
        "-o",
        help="Path to save the modified config (default: original_name_mock.yaml)",
    )
    parser.add_argument(
        "--port",
        "-p",
        type=int,
        default=8000,
        help="Port the mock server is running on (default: 8000)",
    )

    args = parser.parse_args()

    try:
        output_path = modify_config(args.config_path, args.output, args.port)
        print(f"\nSuccess! Run AIPerf with: --config {output_path}")
    except Exception as e:
        print(f"Error modifying config: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
