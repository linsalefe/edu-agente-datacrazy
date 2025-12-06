from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # API
    APP_NAME: str = "WhatsApp AI Agent"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    
    # Database
    DATABASE_URL: str
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # OpenAI
    OPENAI_API_KEY: str
    
    # Z-API
    ZAPI_TOKEN: str
    ZAPI_INSTANCE: str
    ZAPI_BASE_URL: str = "https://api.z-api.io/instances"
    
    # DataCrazy
    DATACRAZY_API_TOKEN: str
    DATACRAZY_BASE_URL: str = "https://crm.datacrazy.io/api/v1"
    
    # Celery
    CELERY_BROKER_URL: Optional[str] = None
    CELERY_RESULT_BACKEND: Optional[str] = None
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()