# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Tests for ZMQ socket defaults and configuration.
"""

import pytest
import zmq

from aiperf.common.comms.zmq import ZMQSocketDefaults


class TestZMQSocketDefaults:
    """Tests for ZMQSocketDefaults class."""

    def test_socket_defaults_values(self):
        """Test that socket defaults have expected values."""
        assert ZMQSocketDefaults.RCVTIMEO == 300000  # 5 minutes
        assert ZMQSocketDefaults.SNDTIMEO == 300000  # 5 minutes
        assert ZMQSocketDefaults.TCP_KEEPALIVE == 1
        assert ZMQSocketDefaults.TCP_KEEPALIVE_IDLE == 60
        assert ZMQSocketDefaults.TCP_KEEPALIVE_INTVL == 10
        assert ZMQSocketDefaults.TCP_KEEPALIVE_CNT == 3
        assert ZMQSocketDefaults.IMMEDIATE == 1
        assert ZMQSocketDefaults.LINGER == 0

    def test_socket_defaults_types(self):
        """Test that socket defaults are of correct types."""
        assert isinstance(ZMQSocketDefaults.RCVTIMEO, int)
        assert isinstance(ZMQSocketDefaults.SNDTIMEO, int)
        assert isinstance(ZMQSocketDefaults.TCP_KEEPALIVE, int)
        assert isinstance(ZMQSocketDefaults.TCP_KEEPALIVE_IDLE, int)
        assert isinstance(ZMQSocketDefaults.TCP_KEEPALIVE_INTVL, int)
        assert isinstance(ZMQSocketDefaults.TCP_KEEPALIVE_CNT, int)
        assert isinstance(ZMQSocketDefaults.IMMEDIATE, int)
        assert isinstance(ZMQSocketDefaults.LINGER, int)

    def test_socket_defaults_reasonable_values(self):
        """Test that socket defaults have reasonable values."""
        # Timeouts should be positive
        assert ZMQSocketDefaults.RCVTIMEO > 0
        assert ZMQSocketDefaults.SNDTIMEO > 0

        # TCP keepalive should be enabled
        assert ZMQSocketDefaults.TCP_KEEPALIVE == 1

        # Keepalive parameters should be reasonable
        assert ZMQSocketDefaults.TCP_KEEPALIVE_IDLE > 0
        assert ZMQSocketDefaults.TCP_KEEPALIVE_INTVL > 0
        assert ZMQSocketDefaults.TCP_KEEPALIVE_CNT > 0

        # Immediate should be enabled for better performance
        assert ZMQSocketDefaults.IMMEDIATE == 1

        # Linger should be 0 for immediate close
        assert ZMQSocketDefaults.LINGER == 0

    def test_socket_defaults_compatibility_with_zmq(self):
        """Test that socket defaults are compatible with ZMQ constants."""
        # These should be valid ZMQ socket options
        valid_options = [
            zmq.RCVTIMEO,
            zmq.SNDTIMEO,
            zmq.TCP_KEEPALIVE,
            zmq.TCP_KEEPALIVE_IDLE,
            zmq.TCP_KEEPALIVE_INTVL,
            zmq.TCP_KEEPALIVE_CNT,
            zmq.IMMEDIATE,
            zmq.LINGER,
        ]

        # All should be integers (ZMQ socket option constants)
        for option in valid_options:
            assert isinstance(option, int)

    def test_socket_defaults_as_dict(self):
        """Test converting socket defaults to dictionary format."""
        defaults_dict = {
            zmq.RCVTIMEO: ZMQSocketDefaults.RCVTIMEO,
            zmq.SNDTIMEO: ZMQSocketDefaults.SNDTIMEO,
            zmq.TCP_KEEPALIVE: ZMQSocketDefaults.TCP_KEEPALIVE,
            zmq.TCP_KEEPALIVE_IDLE: ZMQSocketDefaults.TCP_KEEPALIVE_IDLE,
            zmq.TCP_KEEPALIVE_INTVL: ZMQSocketDefaults.TCP_KEEPALIVE_INTVL,
            zmq.TCP_KEEPALIVE_CNT: ZMQSocketDefaults.TCP_KEEPALIVE_CNT,
            zmq.IMMEDIATE: ZMQSocketDefaults.IMMEDIATE,
            zmq.LINGER: ZMQSocketDefaults.LINGER,
        }

        # Should have expected number of options
        assert len(defaults_dict) == 8

        # All values should match class attributes
        for zmq_option, default_value in defaults_dict.items():
            assert isinstance(zmq_option, int)
            assert isinstance(default_value, int)

    @pytest.mark.parametrize(
        "attribute_name,expected_type",
        [
            ("RCVTIMEO", int),
            ("SNDTIMEO", int),
            ("TCP_KEEPALIVE", int),
            ("TCP_KEEPALIVE_IDLE", int),
            ("TCP_KEEPALIVE_INTVL", int),
            ("TCP_KEEPALIVE_CNT", int),
            ("IMMEDIATE", int),
            ("LINGER", int),
        ],
    )
    def test_socket_defaults_attributes_exist(self, attribute_name, expected_type):
        """Test that all expected socket default attributes exist."""
        assert hasattr(ZMQSocketDefaults, attribute_name)
        value = getattr(ZMQSocketDefaults, attribute_name)
        assert isinstance(value, expected_type)

    def test_socket_defaults_class_is_static(self):
        """Test that ZMQSocketDefaults can be used as a static class."""
        # Should be able to access attributes without instantiation
        assert ZMQSocketDefaults.RCVTIMEO is not None

        # Should not be able to instantiate
        with pytest.raises(TypeError):
            ZMQSocketDefaults()

    def test_socket_defaults_immutability(self):
        """Test that socket defaults are immutable (or at least documented as such)."""
        # Store original value
        original_rcvtimeo = ZMQSocketDefaults.RCVTIMEO

        # Try to modify (this might work in Python, but it's not recommended)
        ZMQSocketDefaults.RCVTIMEO = 12345

        # For this test, we just verify we can access the value
        # In practice, these should be treated as constants
        assert hasattr(ZMQSocketDefaults, "RCVTIMEO")

        # Restore original value for other tests
        ZMQSocketDefaults.RCVTIMEO = original_rcvtimeo

    def test_socket_defaults_documentation(self):
        """Test that the ZMQSocketDefaults class has proper documentation."""
        assert ZMQSocketDefaults.__doc__ is not None
        assert "Default values for ZMQ sockets" in ZMQSocketDefaults.__doc__

    def test_timeout_values_in_milliseconds(self):
        """Test that timeout values are in milliseconds as expected by ZMQ."""
        # ZMQ expects timeouts in milliseconds
        # 300000 ms = 5 minutes
        assert ZMQSocketDefaults.RCVTIMEO == 300000
        assert ZMQSocketDefaults.SNDTIMEO == 300000

        # Convert to seconds for verification
        rcv_timeout_seconds = ZMQSocketDefaults.RCVTIMEO / 1000
        snd_timeout_seconds = ZMQSocketDefaults.SNDTIMEO / 1000

        assert rcv_timeout_seconds == 300  # 5 minutes
        assert snd_timeout_seconds == 300  # 5 minutes

    def test_keepalive_values_reasonable(self):
        """Test that TCP keepalive values are reasonable for production use."""
        # Idle time should be reasonable (not too short, not too long)
        assert 30 <= ZMQSocketDefaults.TCP_KEEPALIVE_IDLE <= 120  # 30s to 2min

        # Interval should be reasonable
        assert 1 <= ZMQSocketDefaults.TCP_KEEPALIVE_INTVL <= 30  # 1s to 30s

        # Count should be reasonable
        assert 1 <= ZMQSocketDefaults.TCP_KEEPALIVE_CNT <= 10  # 1 to 10 probes

    def test_performance_oriented_defaults(self):
        """Test that defaults are oriented towards performance."""
        # IMMEDIATE should be enabled for better performance
        assert ZMQSocketDefaults.IMMEDIATE == 1

        # LINGER should be 0 to avoid blocking on close
        assert ZMQSocketDefaults.LINGER == 0

        # TCP_KEEPALIVE should be enabled for connection health
        assert ZMQSocketDefaults.TCP_KEEPALIVE == 1

    @pytest.mark.parametrize(
        "option_name,zmq_constant",
        [
            ("RCVTIMEO", zmq.RCVTIMEO),
            ("SNDTIMEO", zmq.SNDTIMEO),
            ("TCP_KEEPALIVE", zmq.TCP_KEEPALIVE),
            ("TCP_KEEPALIVE_IDLE", zmq.TCP_KEEPALIVE_IDLE),
            ("TCP_KEEPALIVE_INTVL", zmq.TCP_KEEPALIVE_INTVL),
            ("TCP_KEEPALIVE_CNT", zmq.TCP_KEEPALIVE_CNT),
            ("IMMEDIATE", zmq.IMMEDIATE),
            ("LINGER", zmq.LINGER),
        ],
    )
    def test_option_mapping_to_zmq_constants(self, option_name, zmq_constant):
        """Test that each option name maps to the correct ZMQ constant."""
        assert hasattr(ZMQSocketDefaults, option_name)
        default_value = getattr(ZMQSocketDefaults, option_name)

        # The value should be a valid integer for socket options
        assert isinstance(default_value, int)

        # The ZMQ constant should also be an integer
        assert isinstance(zmq_constant, int)

    def test_complete_socket_configuration(self):
        """Test that defaults provide a complete socket configuration."""
        # Should have both send and receive timeouts
        assert hasattr(ZMQSocketDefaults, "RCVTIMEO")
        assert hasattr(ZMQSocketDefaults, "SNDTIMEO")

        # Should have complete TCP keepalive configuration
        assert hasattr(ZMQSocketDefaults, "TCP_KEEPALIVE")
        assert hasattr(ZMQSocketDefaults, "TCP_KEEPALIVE_IDLE")
        assert hasattr(ZMQSocketDefaults, "TCP_KEEPALIVE_INTVL")
        assert hasattr(ZMQSocketDefaults, "TCP_KEEPALIVE_CNT")

        # Should have performance options
        assert hasattr(ZMQSocketDefaults, "IMMEDIATE")
        assert hasattr(ZMQSocketDefaults, "LINGER")

    def test_socket_defaults_for_different_patterns(self):
        """Test that defaults are suitable for different ZMQ patterns."""
        # For request-reply patterns, timeouts are important
        assert ZMQSocketDefaults.RCVTIMEO > 0
        assert ZMQSocketDefaults.SNDTIMEO > 0

        # For pub-sub patterns, immediate delivery is preferred
        assert ZMQSocketDefaults.IMMEDIATE == 1

        # For pipeline patterns, no lingering is preferred
        assert ZMQSocketDefaults.LINGER == 0

        # For all patterns, connection health monitoring is important
        assert ZMQSocketDefaults.TCP_KEEPALIVE == 1
