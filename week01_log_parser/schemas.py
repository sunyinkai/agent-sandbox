from typing import Optional, Literal
from pydantic import BaseModel, Field


class ParsedError(BaseModel):
    error_type: str = Field(
        description="The Python exception type, such as AttributeError or TypeError."
    )
    file_path: Optional[str] = Field(
        default=None, description="The file path where the error occurred."
    )
    line_number: Optional[int] = Field(
        default=None, description="The line number where the error occurred."
    )
    function_name: Optional[str] = Field(
        default=None,
        description="The function or method name where the error occurred.",
    )
    raw_message: str = Field(description="The raw exception message.")
    likely_cause: Optional[str] = Field(
        default=None, description="A short explanation of the likely cause."
    )
    severity: Literal["low", "medium", "high"] = Field(
        description="Estimated severity of the error."
    )
