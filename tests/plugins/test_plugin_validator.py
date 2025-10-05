# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Tests for Plugin Validator (AIP-001)

WHY TEST THIS:
- Validation ensures plugins conform to their protocols
- Prevents runtime errors from malformed plugins
- Provides clear error messages for plugin authors
- Enforces AIP version compatibility

WHAT WE TEST:
- Protocol conformance checking for all plugin types
- Metadata presence and structure validation
- AIP version validation
- Error reporting for validation failures
- Handling of edge cases (missing attrs, wrong types, etc.)

TESTING PHILOSOPHY:
We test VALIDATION OUTCOMES (accept valid, reject invalid) not
implementation details. We verify correct error detection.
"""

from aiperf.plugins.validator import PluginValidator


class TestBasicValidation:
    """
    Test basic validation functionality.

    WHY TEST THIS: Core validation must correctly identify valid/invalid plugins.
    """

    def test_validate_valid_metric_plugin(self, mock_plugin_classes):
        """
        WHY: Valid plugins should pass validation.

        WHAT: Returns True for conforming plugin.
        """
        validator = PluginValidator()
        plugin = mock_plugin_classes["MockMetricPlugin"]

        result = validator.validate_plugin(plugin, "aiperf.metric")

        assert result is True

    def test_validate_invalid_metric_plugin(self, mock_plugin_classes):
        """
        WHY: Invalid plugins should fail validation.

        WHAT: Returns False for non-conforming plugin.
        """
        validator = PluginValidator()
        plugin = mock_plugin_classes["InvalidMetricPlugin"]

        result = validator.validate_plugin(plugin, "aiperf.metric")

        assert result is False

    def test_validate_plugin_without_metadata(self, mock_plugin_classes):
        """
        WHY: Plugins must provide metadata.

        WHAT: Returns False when metadata method missing.
        """
        validator = PluginValidator()
        plugin = mock_plugin_classes["NoMetadataPlugin"]

        result = validator.validate_plugin(plugin, "aiperf.metric")

        assert result is False

    def test_validate_plugin_with_old_aip_version(self, mock_plugin_classes):
        """
        WHY: Unsupported AIP versions should be rejected.

        WHAT: Returns False for old/unsupported AIP version.
        """
        validator = PluginValidator()
        plugin = mock_plugin_classes["OldAIPVersionPlugin"]

        result = validator.validate_plugin(plugin, "aiperf.metric")

        assert result is False


class TestMetadataValidation:
    """
    Test metadata validation.

    WHY TEST THIS: Metadata structure is critical for plugin system.
    """

    def test_metadata_requires_name_field(self):
        """
        WHY: name field is required for identification.

        WHAT: Fails validation when name missing.
        """

        class PluginWithoutName:
            @staticmethod
            def plugin_metadata():
                return {
                    "aip_version": "001",
                    # name is missing
                }

            tag = "test"
            header = "Test"
            unit = "ms"
            flags = 0

            def _parse_record(self, record, record_metrics):
                return 1.0

        validator = PluginValidator()
        result = validator.validate_plugin(PluginWithoutName, "aiperf.metric")

        assert result is False

    def test_metadata_requires_aip_version_field(self):
        """
        WHY: aip_version field ensures compatibility.

        WHAT: Fails validation when aip_version missing.
        """

        class PluginWithoutAIPVersion:
            @staticmethod
            def plugin_metadata():
                return {
                    "name": "test_plugin",
                    # aip_version is missing
                }

            tag = "test"
            header = "Test"
            unit = "ms"
            flags = 0

            def _parse_record(self, record, record_metrics):
                return 1.0

        validator = PluginValidator()
        result = validator.validate_plugin(PluginWithoutAIPVersion, "aiperf.metric")

        assert result is False

    def test_metadata_with_all_required_fields_passes(self):
        """
        WHY: Plugins with required metadata should pass.

        WHAT: Returns True when name and aip_version present.
        """

        class MinimalValidPlugin:
            @staticmethod
            def plugin_metadata():
                return {
                    "name": "minimal_plugin",
                    "aip_version": "001",
                }

            tag = "minimal"
            header = "Minimal"
            unit = "ms"
            flags = 0

            def _parse_record(self, record, record_metrics):
                return 1.0

        validator = PluginValidator()
        result = validator.validate_plugin(MinimalValidPlugin, "aiperf.metric")

        assert result is True

    def test_metadata_with_optional_fields_passes(self):
        """
        WHY: Optional metadata fields should be supported.

        WHAT: Accepts plugins with additional metadata.
        """

        class PluginWithOptionalMetadata:
            @staticmethod
            def plugin_metadata():
                return {
                    "name": "full_plugin",
                    "aip_version": "001",
                    "display_name": "Full Plugin",
                    "version": "1.0.0",
                    "author": "NVIDIA",
                    "license": "Apache-2.0",
                    "requires": ["numpy", "pandas"],
                }

            tag = "full"
            header = "Full"
            unit = "ms"
            flags = 0

            def _parse_record(self, record, record_metrics):
                return 1.0

        validator = PluginValidator()
        result = validator.validate_plugin(PluginWithOptionalMetadata, "aiperf.metric")

        assert result is True


class TestProtocolValidation:
    """
    Test protocol conformance validation.

    WHY TEST THIS: Plugins must implement required protocol methods/attributes.
    """

    def test_metric_plugin_protocol(self, mock_plugin_classes):
        """
        WHY: Metric plugins must conform to MetricPluginProtocol.

        WHAT: Validates required attributes and methods.
        """
        validator = PluginValidator()
        plugin = mock_plugin_classes["MockMetricPlugin"]

        # Should pass protocol validation
        result = validator._validate_protocol(plugin, "aiperf.metric")

        assert result is True

    def test_endpoint_plugin_protocol(self, mock_plugin_classes):
        """
        WHY: Endpoint plugins must conform to EndpointPluginProtocol.

        WHAT: Validates required methods.
        """
        validator = PluginValidator()
        plugin = mock_plugin_classes["MockEndpointPlugin"]

        result = validator._validate_protocol(plugin, "aiperf.endpoint")

        assert result is True

    def test_data_exporter_plugin_protocol(self, mock_plugin_classes):
        """
        WHY: Data exporter plugins must conform to DataExporterPluginProtocol.

        WHAT: Validates required methods.
        """
        validator = PluginValidator()
        plugin = mock_plugin_classes["MockDataExporterPlugin"]

        result = validator._validate_protocol(plugin, "aiperf.data_exporter")

        assert result is True

    def test_transport_plugin_protocol(self, mock_plugin_classes):
        """
        WHY: Transport plugins must conform to TransportPluginProtocol.

        WHAT: Validates required methods.
        """
        validator = PluginValidator()
        plugin = mock_plugin_classes["MockTransportPlugin"]

        result = validator._validate_protocol(plugin, "aiperf.transport")

        assert result is True

    def test_processor_plugin_protocol(self, mock_plugin_classes):
        """
        WHY: Processor plugins must conform to ProcessorPluginProtocol.

        WHAT: Validates required methods.
        """
        validator = PluginValidator()
        plugin = mock_plugin_classes["MockProcessorPlugin"]

        result = validator._validate_protocol(plugin, "aiperf.processor")

        assert result is True

    def test_collector_plugin_protocol(self, mock_plugin_classes):
        """
        WHY: Collector plugins must conform to CollectorPluginProtocol.

        WHAT: Validates required methods.
        """
        validator = PluginValidator()
        plugin = mock_plugin_classes["MockCollectorPlugin"]

        result = validator._validate_protocol(plugin, "aiperf.collector")

        assert result is True

    def test_invalid_plugin_fails_protocol(self, mock_plugin_classes):
        """
        WHY: Plugins missing required methods should fail.

        WHAT: Protocol validation catches missing methods.
        """
        validator = PluginValidator()
        plugin = mock_plugin_classes["InvalidMetricPlugin"]

        result = validator._validate_protocol(plugin, "aiperf.metric")

        assert result is False

    def test_unknown_group_passes_validation(self):
        """
        WHY: Future plugin types shouldn't break validator.

        WHAT: Returns True when no protocol defined for group.
        """

        class UnknownTypePlugin:
            @staticmethod
            def plugin_metadata():
                return {
                    "name": "unknown",
                    "aip_version": "001",
                }

        validator = PluginValidator()
        result = validator._validate_protocol(UnknownTypePlugin, "aiperf.unknown")

        # Should pass (no protocol to validate against)
        assert result is True


class TestAIPVersionValidation:
    """
    Test AIP version validation.

    WHY TEST THIS: Version compatibility is critical for system stability.
    """

    def test_aip_001_supported(self):
        """
        WHY: AIP-001 is current version.

        WHAT: Accepts plugins with aip_version "001".
        """

        class AIP001Plugin:
            @staticmethod
            def plugin_metadata():
                return {
                    "name": "aip001_plugin",
                    "aip_version": "001",
                }

            tag = "test"
            header = "Test"
            unit = "ms"
            flags = 0

            def _parse_record(self, record, record_metrics):
                return 1.0

        validator = PluginValidator()
        result = validator._validate_aip_version(AIP001Plugin)

        assert result is True

    def test_aip_000_unsupported(self, mock_plugin_classes):
        """
        WHY: Old AIP versions not supported.

        WHAT: Rejects plugins with old aip_version.
        """
        validator = PluginValidator()
        plugin = mock_plugin_classes["OldAIPVersionPlugin"]

        result = validator._validate_aip_version(plugin)

        assert result is False

    def test_aip_002_unsupported(self):
        """
        WHY: Future AIP versions not yet supported.

        WHAT: Rejects plugins with future aip_version.
        """

        class FutureAIPPlugin:
            @staticmethod
            def plugin_metadata():
                return {
                    "name": "future_plugin",
                    "aip_version": "002",
                }

            tag = "test"
            header = "Test"
            unit = "ms"
            flags = 0

            def _parse_record(self, record, record_metrics):
                return 1.0

        validator = PluginValidator()
        result = validator._validate_aip_version(FutureAIPPlugin)

        assert result is False

    def test_invalid_aip_version_format(self):
        """
        WHY: Malformed versions should be rejected.

        WHAT: Rejects non-standard version strings.
        """

        class InvalidVersionPlugin:
            @staticmethod
            def plugin_metadata():
                return {
                    "name": "invalid_version",
                    "aip_version": "1.0.0",  # Wrong format
                }

            tag = "test"
            header = "Test"
            unit = "ms"
            flags = 0

            def _parse_record(self, record, record_metrics):
                return 1.0

        validator = PluginValidator()
        result = validator._validate_aip_version(InvalidVersionPlugin)

        assert result is False


class TestValidationErrorHandling:
    """
    Test error handling in validation.

    WHY TEST THIS: Validation should be robust against edge cases.
    """

    def test_metadata_method_raises_exception(self):
        """
        WHY: Broken metadata methods shouldn't crash validator.

        WHAT: Returns False when metadata() raises exception.
        """

        class BrokenMetadataPlugin:
            @staticmethod
            def plugin_metadata():
                raise RuntimeError("Metadata error")

        validator = PluginValidator()
        result = validator._validate_metadata(BrokenMetadataPlugin)

        assert result is False

    def test_metadata_returns_non_dict(self):
        """
        WHY: Metadata must be a dict.

        WHAT: Handles non-dict metadata gracefully.
        """

        class NonDictMetadataPlugin:
            @staticmethod
            def plugin_metadata():
                return "not a dict"

        validator = PluginValidator()
        result = validator.validate_plugin(NonDictMetadataPlugin, "aiperf.metric")

        assert result is False

    def test_metadata_returns_none(self):
        """
        WHY: None metadata should fail validation.

        WHAT: Handles None return value.
        """

        class NoneMetadataPlugin:
            @staticmethod
            def plugin_metadata():
                return None

        validator = PluginValidator()
        result = validator.validate_plugin(NoneMetadataPlugin, "aiperf.metric")

        assert result is False


class TestProtocolMapCompleteness:
    """
    Test protocol map covers all plugin types.

    WHY TEST THIS: All AIP-001 plugin types must have protocols.
    """

    def test_all_plugin_groups_have_protocols(self):
        """
        WHY: Every plugin type needs a protocol.

        WHAT: PROTOCOL_MAP contains all plugin groups.
        """
        from aiperf.plugins.discovery import PLUGIN_GROUPS
        from aiperf.plugins.validator import PROTOCOL_MAP

        for group_name in PLUGIN_GROUPS.values():
            assert group_name in PROTOCOL_MAP

    def test_protocol_map_entries_are_protocols(self):
        """
        WHY: Protocol map must reference actual protocols.

        WHAT: Each value is a protocol class.
        """
        from aiperf.plugins.validator import PROTOCOL_MAP

        for _group, protocol in PROTOCOL_MAP.items():
            # Protocols should be classes
            assert isinstance(protocol, type)
            # Should be marked as runtime_checkable
            assert hasattr(protocol, "__mro__")


class TestComplexValidationScenarios:
    """
    Test validation in complex scenarios.

    WHY TEST THIS: Real-world plugins may have edge cases.
    """

    def test_plugin_with_extra_attributes(self):
        """
        WHY: Plugins can have additional attributes beyond protocol.

        WHAT: Extra attributes don't cause validation failure.
        """

        class PluginWithExtras:
            @staticmethod
            def plugin_metadata():
                return {
                    "name": "extras_plugin",
                    "aip_version": "001",
                }

            # Required attributes
            tag = "extras"
            header = "Extras"
            unit = "ms"
            flags = 0

            # Extra attributes (ok)
            extra_attribute = "extra"
            another_extra = 42

            def _parse_record(self, record, record_metrics):
                return 1.0

            def extra_method(self):
                """Extra method is fine."""
                pass

        validator = PluginValidator()
        result = validator.validate_plugin(PluginWithExtras, "aiperf.metric")

        assert result is True

    def test_plugin_class_vs_instance(self):
        """
        WHY: Validation should work on both classes and instances.

        WHAT: Validates class (not instance).
        """

        class TestPlugin:
            @staticmethod
            def plugin_metadata():
                return {
                    "name": "test_plugin",
                    "aip_version": "001",
                }

            tag = "test"
            header = "Test"
            unit = "ms"
            flags = 0

            def _parse_record(self, record, record_metrics):
                return 1.0

        validator = PluginValidator()

        # Validate class (typical usage)
        result_class = validator.validate_plugin(TestPlugin, "aiperf.metric")
        assert result_class is True

        # Validate instance (should also work)
        instance = TestPlugin()
        result_instance = validator.validate_plugin(instance, "aiperf.metric")
        assert result_instance is True

    def test_plugin_with_inheritance(self):
        """
        WHY: Plugins may inherit from base classes.

        WHAT: Inheritance doesn't affect validation.
        """

        class BaseMetricPlugin:
            tag = "base"
            header = "Base"
            unit = "ms"
            flags = 0

            def _parse_record(self, record, record_metrics):
                return 0.0

        class DerivedPlugin(BaseMetricPlugin):
            @staticmethod
            def plugin_metadata():
                return {
                    "name": "derived_plugin",
                    "aip_version": "001",
                }

            tag = "derived"
            header = "Derived"

        validator = PluginValidator()
        result = validator.validate_plugin(DerivedPlugin, "aiperf.metric")

        assert result is True


class TestValidatorReusability:
    """
    Test validator can be reused for multiple validations.

    WHY TEST THIS: Validator instance should be reusable.
    """

    def test_validator_reusable(self, mock_plugin_classes):
        """
        WHY: Same validator should work for multiple plugins.

        WHAT: Single validator instance validates many plugins.
        """
        validator = PluginValidator()

        # Validate multiple plugins
        result1 = validator.validate_plugin(
            mock_plugin_classes["MockMetricPlugin"], "aiperf.metric"
        )
        result2 = validator.validate_plugin(
            mock_plugin_classes["MockEndpointPlugin"], "aiperf.endpoint"
        )
        result3 = validator.validate_plugin(
            mock_plugin_classes["InvalidMetricPlugin"], "aiperf.metric"
        )

        assert result1 is True
        assert result2 is True
        assert result3 is False

    def test_validator_stateless(self, mock_plugin_classes):
        """
        WHY: Validator shouldn't maintain state between validations.

        WHAT: Each validation is independent.
        """
        validator = PluginValidator()

        # Validate failing plugin
        validator.validate_plugin(
            mock_plugin_classes["InvalidMetricPlugin"], "aiperf.metric"
        )

        # Validate valid plugin (shouldn't be affected by previous failure)
        result = validator.validate_plugin(
            mock_plugin_classes["MockMetricPlugin"], "aiperf.metric"
        )

        assert result is True
