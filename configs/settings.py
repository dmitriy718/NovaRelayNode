from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    api_key: str = Field(..., env="API_KEY")
    signing_secret: str = Field(..., env="SIGNING_SECRET")
    rate_limit_per_minute: int = Field(60, env="RATE_LIMIT_PER_MINUTE")
    redis_url: str = Field("redis://redis:6379/0", env="REDIS_URL")
    queue_name: str = Field("alerts", env="QUEUE_NAME")
    idempotency_ttl_seconds: int = Field(86_400, env="IDEMPOTENCY_TTL_SECONDS")
    max_retry_attempts: int = Field(5, env="MAX_RETRY_ATTEMPTS")

    telegram_bot_token: str | None = Field(None, env="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: str | None = Field(None, env="TELEGRAM_CHAT_ID")
    discord_webhook_url: str | None = Field(None, env="DISCORD_WEBHOOK_URL")

    smtp_host: str | None = Field(None, env="SMTP_HOST")
    smtp_port: int = Field(587, env="SMTP_PORT")
    smtp_username: str | None = Field(None, env="SMTP_USERNAME")
    smtp_password: str | None = Field(None, env="SMTP_PASSWORD")
    smtp_from: str | None = Field(None, env="SMTP_FROM")
    smtp_to: str | None = Field(None, env="SMTP_TO")

    twilio_account_sid: str | None = Field(None, env="TWILIO_ACCOUNT_SID")
    twilio_auth_token: str | None = Field(None, env="TWILIO_AUTH_TOKEN")
    twilio_from: str | None = Field(None, env="TWILIO_FROM")
    twilio_to: str | None = Field(None, env="TWILIO_TO")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
