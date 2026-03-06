from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    APP_NAME: str = "TouristApp"
    APP_ENV: str = "development"
    SECRET_KEY: str = "venuboy267"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    MONGODB_URL: str = "mongodb+srv://Natravels:zero8907@cluster0.x8s6sie.mongodb.net/?appName=Cluster0"
    DATABASE_NAME: str = "tourist_db"

    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = "natravelsoffcail@gmail.com"
    SMTP_PASSWORD: str = "qpha qkbn rytr ncvu"
    EMAIL_FROM: str = "natravelsoffcail@gmail.com"
    EMAIL_FROM_NAME: str = "TouristApp"

    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""

    FRONTEND_URL: str = "http://localhost:3000"
    MAX_FILE_SIZE_MB: int = 10
    UPLOAD_DIR: str = "uploads"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
