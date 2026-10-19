"""Configuracion del Fiscal Agent API."""

import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "openai")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    ANTHROPIC_MODEL: str = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "*")
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    # Plan P — persistencia relacional (DP-1). Railway inyecta DATABASE_URL de Postgres.
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./fiscalito.db").replace(
        "postgres://", "postgresql+psycopg://", 1
    ).replace("postgresql://", "postgresql+psycopg://", 1)
    # Llave maestra (Fernet, base64 de 32 bytes) con la que se cifran e.firma y CSD.
    LLAVE_MAESTRA: str = os.getenv("FISCALITO_LLAVE_MAESTRA", "")
    # Entorno: "desarrollo" permite atajos locales; "produccion" los prohíbe todos.
    # Falla cerrado: con Postgres y sin la variable, se asume producción (sin atajos, sin
    # implementaciones falsas, sin llave efímera, sin create_all).
    ENTORNO: str = os.getenv(
        "FISCALITO_ENTORNO",
        "produccion" if os.getenv("DATABASE_URL", "").startswith("postgres") else "desarrollo",
    )


settings = Settings()
