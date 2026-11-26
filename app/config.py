"""Load app settings from .env into one typed object."""
import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    """All configuration the app needs. frozen=True makes it read-only."""

    coc_api_key: str
    clan_tag: str
    database_url: str
    poll_minutes: int

    def __repr__(self) -> str:
        """Hide the API key so printing settings never leaks it."""
        return (
            f"Settings(coc_api_key='***', clan_tag={self.clan_tag!r}, "
            f"database_url={self.database_url!r}, poll_minutes={self.poll_minutes})"
        )


def get_settings() -> Settings:
    """Read .env and environment variables, validate them, return Settings."""
    load_dotenv()

    api_key = os.getenv("COC_API_KEY")
    clan_tag = os.getenv("CLAN_TAG")
    if not api_key or not clan_tag:
        raise RuntimeError("COC_API_KEY and CLAN_TAG must be set in .env")

    poll_minutes = int(os.getenv("POLL_MINUTES", "10"))
    if poll_minutes < 5:
        raise RuntimeError("POLL_MINUTES must be at least 5 (respect the API)")

    return Settings(
        coc_api_key=api_key,
        clan_tag=clan_tag,
        database_url=os.getenv("DATABASE_URL", "sqlite:///clanpulse.db"),
        poll_minutes=poll_minutes,
    )
