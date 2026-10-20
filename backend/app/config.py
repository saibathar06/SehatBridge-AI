import base64
from functools import lru_cache
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore', hide_input_in_errors=True)
    environment: str = 'development'
    database_url: str = 'sqlite:///./sehatbridge.db'
    redis_url: str = ''
    jwt_secret: str
    encryption_key: str
    otp_secret: str
    access_minutes: int = 15
    refresh_days: int = 30
    otp_provider: str = 'console'
    smtp_host: str = ''
    smtp_port: int = 587
    smtp_username: str = ''
    smtp_password: str = ''
    smtp_from: str = ''
    gemini_api_key: str = ''
    gemini_model: str = ''
    ai_timeout_seconds: int = 60
    ai_max_output_tokens: int = 8192
    storage_path: str = './storage'
    max_upload_mb: int = 20
    max_pages: int = 40
    extraction_batch_pages: int = 5
    cors_origins: list[str] = []
    firebase_credentials: str = ''
    demo_enabled: bool = True
    rate_limit_per_minute: int = 90
    log_level: str = 'warning'
    recaptcha_enabled: bool = False
    recaptcha_site_key: str = ''
    recaptcha_secret_key: str = ''
    recaptcha_public_origin: str = ''
    recaptcha_allowed_hostnames: list[str] = []

    @model_validator(mode='after')
    def secure_config(self):
        if self.recaptcha_enabled:
            from urllib.parse import urlsplit
            import re
            origin = urlsplit(self.recaptcha_public_origin)
            if (origin.scheme not in ('http', 'https') or not origin.hostname or
                    origin.username or origin.password or origin.path not in ('', '/') or origin.query or origin.fragment):
                raise ValueError('RECAPTCHA_PUBLIC_ORIGIN must be an HTTP(S) origin without credentials or a path')
            if not re.fullmatch(r'[A-Za-z0-9_-]{10,256}', self.recaptcha_site_key) or not self.recaptcha_secret_key:
                raise ValueError('Enabled reCAPTCHA requires a v2 checkbox site key and server secret')
            if origin.hostname.lower() not in self.recaptcha_allowed_hostnames:
                raise ValueError('The CAPTCHA page hostname must be explicitly listed in RECAPTCHA_ALLOWED_HOSTNAMES')
            if self.environment == 'production' and (origin.scheme != 'https' or origin.hostname in ('localhost', '127.0.0.1', '::1')):
                raise ValueError('Production CAPTCHA requires a public HTTPS origin')
            if self.environment == 'production' and self.recaptcha_site_key == '6LeIxAcTAAAAAJcZVRqyHh71UMIEGNQ_MXjiZKhI':
                raise ValueError('Google test CAPTCHA keys cannot be used in production')
        if len(self.jwt_secret) < 32 or len(self.otp_secret) < 32:
            raise ValueError('Token and OTP secrets must have at least 32 characters')
        if len(base64.urlsafe_b64decode(self.encryption_key)) != 32:
            raise ValueError('ENCRYPTION_KEY must be URL-safe base64 of 32 random bytes')
        if self.environment == 'production':
            if not self.recaptcha_enabled:
                raise ValueError('Production requires reCAPTCHA protection')
            if self.otp_provider != 'smtp' or not self.smtp_host or not self.redis_url:
                raise ValueError('Production requires SMTP OTP delivery and Redis')
            if not self.database_url.startswith('postgresql'):
                raise ValueError('Production requires PostgreSQL')
        return self


@lru_cache
def settings():
    return Settings()
