from typing import Optional
from pydantic import BaseModel, ConfigDict, Field

class SystemSettings(BaseModel):
    """
    アプリケーション全体のシステム設定を管理するドメインモデル
    将来的な拡張（Gemini API Keyなど）を見据えた構造。
    """
    id: Optional[int] = Field(None, description="Database ID")
    openai_api_key: Optional[str] = Field(None, description="OpenAI / Gemini API Key for AI operations")
    
    model_config = ConfigDict(from_attributes=True, extra='forbid')
