from typing import Optional, Union

from pydantic import BaseModel, Field

from aiperf.common.enums import StrEnum


class ZMQTransportProtocol(StrEnum):
    """Transport protocol for ZMQ communication."""

    TCP = "tcp"
    INPROC = "inproc"


class TCPTransportConfig(BaseModel):
    """Configuration for TCP transport."""

    host: str = Field(
        default="127.0.0.1",
        description="Host address for TCP connections",
    )
    controller_pub_sub_port: int = Field(
        default=5555, description="Port for controller pub/sub messages"
    )
    component_pub_sub_port: int = Field(
        default=5556, description="Port for component pub/sub messages"
    )
    inference_pub_sub_port: int = Field(
        default=5557, description="Port for inference pub/sub messages"
    )
    req_rep_port: int = Field(
        default=5558, description="Port for sending and receiving requests"
    )
    push_pull_port: int = Field(
        default=5559, description="Port for pushing and pulling data"
    )
    records_port: int = Field(default=5560, description="Port for record data")
    conversation_data_port: int = Field(
        default=5561, description="Port for conversation data"
    )
    credit_drop_port: int = Field(
        default=5562, description="Port for credit drop operations"
    )
    credit_return_port: int = Field(
        default=5563, description="Port for credit return operations"
    )


class InprocTransportConfig(BaseModel):
    """Configuration for inproc transport."""

    channel_prefix: str = Field(
        default="aiperf", description="Prefix for inproc channels"
    )


class ZMQCommunicationConfig(BaseModel):
    """Configuration for ZMQ communication."""

    protocol: ZMQTransportProtocol = Field(
        default=ZMQTransportProtocol.TCP,
        description="Transport protocol to use for ZMQ communication",
    )
    protocol_config: Union[TCPTransportConfig, InprocTransportConfig] = Field(
        default_factory=TCPTransportConfig,
        description="Configuration for the selected transport protocol",
    )
    client_id: Optional[str] = Field(
        default=None, description="Client ID, will be generated if not provided"
    )

    @property
    def controller_pub_sub_address(self) -> str:
        """Get the controller pub/sub address based on protocol."""
        if self.protocol == ZMQTransportProtocol.INPROC:
            inproc_config = self.protocol_config
            assert isinstance(inproc_config, InprocTransportConfig)
            return f"inproc://{inproc_config.channel_prefix}_controller"
        tcp_config = self.protocol_config
        assert isinstance(tcp_config, TCPTransportConfig)
        return f"tcp://{tcp_config.host}:{tcp_config.controller_pub_sub_port}"

    @property
    def component_pub_sub_address(self) -> str:
        """Get the component pub/sub address based on protocol."""
        if self.protocol == ZMQTransportProtocol.INPROC:
            inproc_config = self.protocol_config
            assert isinstance(inproc_config, InprocTransportConfig)
            return f"inproc://{inproc_config.channel_prefix}_component"
        tcp_config = self.protocol_config
        assert isinstance(tcp_config, TCPTransportConfig)
        return f"tcp://{tcp_config.host}:{tcp_config.component_pub_sub_port}"

    @property
    def inference_pub_sub_address(self) -> str:
        """Get the inference pub/sub address based on protocol."""
        if self.protocol == ZMQTransportProtocol.INPROC:
            inproc_config = self.protocol_config
            assert isinstance(inproc_config, InprocTransportConfig)
            return f"inproc://{inproc_config.channel_prefix}_inference"
        tcp_config = self.protocol_config
        assert isinstance(tcp_config, TCPTransportConfig)
        return f"tcp://{tcp_config.host}:{tcp_config.inference_pub_sub_port}"

    @property
    def records_address(self) -> str:
        """Get the records address based on protocol."""
        if self.protocol == ZMQTransportProtocol.INPROC:
            inproc_config = self.protocol_config
            assert isinstance(inproc_config, InprocTransportConfig)
            return f"inproc://{inproc_config.channel_prefix}_records"
        tcp_config = self.protocol_config
        assert isinstance(tcp_config, TCPTransportConfig)
        return f"tcp://{tcp_config.host}:{tcp_config.records_port}"

    @property
    def conversation_data_address(self) -> str:
        """Get the conversation data address based on protocol."""
        if self.protocol == ZMQTransportProtocol.INPROC:
            inproc_config = self.protocol_config
            assert isinstance(inproc_config, InprocTransportConfig)
            return f"inproc://{inproc_config.channel_prefix}_conversation_data"
        tcp_config = self.protocol_config
        assert isinstance(tcp_config, TCPTransportConfig)
        return f"tcp://{tcp_config.host}:{tcp_config.conversation_data_port}"

    @property
    def credit_drop_address(self) -> str:
        """Get the credit drop address based on protocol."""
        if self.protocol == ZMQTransportProtocol.INPROC:
            inproc_config = self.protocol_config
            assert isinstance(inproc_config, InprocTransportConfig)
            return f"inproc://{inproc_config.channel_prefix}_credit_drop"
        tcp_config = self.protocol_config
        assert isinstance(tcp_config, TCPTransportConfig)
        return f"tcp://{tcp_config.host}:{tcp_config.credit_drop_port}"

    @property
    def credit_return_address(self) -> str:
        """Get the credit return address based on protocol."""
        if self.protocol == ZMQTransportProtocol.INPROC:
            inproc_config = self.protocol_config
            assert isinstance(inproc_config, InprocTransportConfig)
            return f"inproc://{inproc_config.channel_prefix}_credit_return"
        tcp_config = self.protocol_config
        assert isinstance(tcp_config, TCPTransportConfig)
        return f"tcp://{tcp_config.host}:{tcp_config.credit_return_port}"
