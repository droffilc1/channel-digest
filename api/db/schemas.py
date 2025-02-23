from pydantic import BaseModel
from typing import List


class Setting(BaseModel):
    label: str
    type: str
    required: bool
    default: str


class DigestPayload(BaseModel):
    channel_id: str
    return_url: str
    organisation_id: str
    settings: List[Setting]
