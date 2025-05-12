from pydantic import BaseModel, Field


class CreditDrop(BaseModel):
    """Model for a credit drop."""

    amount: int = Field(..., description="Amount of credits to drop")
    timestamp: float = Field(..., description="Timestamp of the credit drop")


class CreditDropResponse(BaseModel):
    """Model for a credit drop response."""

    success: bool = Field(..., description="Whether the credit drop was successful")
    message: str = Field(..., description="Message from the credit drop")


class CreditReturn(BaseModel):
    """Model for a credit return."""

    amount: int = Field(..., description="Amount of credits to return")


class CreditReturnResponse(BaseModel):
    """Model for a credit return response."""

    success: bool = Field(..., description="Whether the credit return was successful")
    message: str = Field(..., description="Message from the credit return")
