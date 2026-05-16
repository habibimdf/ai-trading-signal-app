from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "AI Trading Signal Assistant"
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    database_url: str = "sqlite:///./signals.db"

    enable_scheduler: bool = False
    scan_interval_minutes: int = 60
    active_pairs: str = "EUR_USD,GBP_USD,USD_JPY,XAU_USD,BTC_USDT"
    default_mode: str = "swing"
    default_balance: float = 1000.0
    default_account_type: str = "USD"
    default_risk_percent: float = 1.0
    min_confidence: int = 70

    data_provider: str = "tradingview"
    tradingview_webhook_secret: str = ""

    enable_ai_reasoning: bool = False
    ai_provider: str = "gemini"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3-flash-preview"
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    gemini_thinking_level: str = "low"

    # Legacy OpenAI settings. Set AI_PROVIDER=openai to use these.
    openai_api_key: str = ""
    openai_model: str = "gpt-5.2"
    openai_base_url: str = "https://api.openai.com/v1"

    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    whatsapp_access_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_to_number: str = ""
    whatsapp_api_version: str = "v23.0"
    whatsapp_use_template: bool = False
    whatsapp_template_name: str = "trading_signal_alert"
    whatsapp_template_language: str = "id"

    def pairs_list(self) -> list[str]:
        return [p.strip().upper() for p in self.active_pairs.split(",") if p.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
