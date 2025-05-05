class AIPerfException(Exception):
    """Base class for all exceptions raised by AIPerf."""


class ConfigurationException(AIPerfException):
    """Exception raised for configuration errors."""
