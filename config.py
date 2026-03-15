import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    rd_obras_base_url: str = field(default_factory=lambda: os.getenv("RD_OBRAS_BASE_URL", "https://api.rdobras.com.br"))
    rd_obras_app_key: str = field(default_factory=lambda: os.getenv("RD_OBRAS_APP_KEY", ""))
    rd_obras_app_secret: str = field(default_factory=lambda: os.getenv("RD_OBRAS_APP_SECRET", ""))

    wts_api_base_url: str = field(default_factory=lambda: os.getenv("WTS_API_BASE_URL", "https://api.wts.chat"))
    wts_api_token: str = field(default_factory=lambda: os.getenv("WTS_API_TOKEN", ""))
    wts_from_phone: str = field(default_factory=lambda: os.getenv("WTS_FROM_PHONE", ""))
    wts_recipient_phone: str = field(default_factory=lambda: os.getenv("WTS_RECIPIENT_PHONE", ""))

    report_hour: int = field(default_factory=lambda: int(os.getenv("REPORT_HOUR", "18")))
    report_minute: int = field(default_factory=lambda: int(os.getenv("REPORT_MINUTE", "0")))
    timezone: str = field(default_factory=lambda: os.getenv("TIMEZONE", "America/Sao_Paulo"))
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))

    ignored_projects: list[str] = field(default_factory=lambda: [
        p.strip().upper()
        for p in os.getenv("IGNORED_PROJECTS", "ESCRITÓRIO").split(",")
        if p.strip()
    ])

    health_check_port: int = 8080
    max_whatsapp_chars: int = 60_000
    rate_limit_delay: float = 0.2
    http_timeout: float = 30.0
    retry_attempts: int = 3


config = Config()
