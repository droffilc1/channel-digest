from pydantic import BaseModel, ConfigDict, field_validator
from typing import List, Optional


class Setting(BaseModel):
    label: str
    type: str
    required: bool
    default: str


class DigestPayload(BaseModel):
    organisation_id: str
    channel_id: str
    return_url: str
    settings: List[Setting]

    # Optional fields with defaults
    interval: Optional[str] = "0 * * * *"
    event_name: Optional[str] = "Channel Digest Report"

    # Allow extra fields
    model_config = ConfigDict(extra="allow")

    # Validators to ensure fields are not None and cast to string
    @field_validator("organisation_id", "channel_id", "return_url", mode="before")
    @classmethod
    def ensure_string(cls, v):
        if v is None:
            raise ValueError("Cannot be None")
        return str(v)
