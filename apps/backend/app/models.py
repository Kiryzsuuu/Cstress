from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


Role = Literal["user", "assistant", "system"]


class ChatMessage(BaseModel):
    role: Role = "user"
    content: str = Field(min_length=1)


class FaceSignals(BaseModel):
    enabled: bool = True
    stressIndex: Optional[float] = Field(default=None, ge=0, le=100)
    level: Optional[str] = None
    blinkPerMin: Optional[float] = Field(default=None, ge=0, le=120)
    jawOpenness: Optional[float] = Field(default=None, ge=0, le=1)
    browTension: Optional[float] = Field(default=None, ge=0, le=1)


class ChatStreamRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1)
    faceSignals: Optional[FaceSignals] = None
