from __future__ import annotations

from pydantic import BaseModel


class CompanyNormalizeRequest(BaseModel):
    text: str
