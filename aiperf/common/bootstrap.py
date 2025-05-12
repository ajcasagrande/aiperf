from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.service.base import ServiceBase


def bootstrap_and_run_service(
    service_class: type[ServiceBase], config: ServiceConfig | None = None
):
    """Bootstrap the service and run it.

    This function will load the service configuration, create an instance of the service,
    and run it.

    Args:
        service_class: The service class of the service to run
        config: The service configuration to use, if not provided, the service configuration
                will be loaded from the config file

    """
    import uvloop

    uvloop.install()

    # Load the service configuration
    if config is None:
        from aiperf.common.config.loader import load_service_config

        config = load_service_config()

    # service_type is filled in by all the service class implementations
    service = service_class(config=config)
    uvloop.run(service.run())
