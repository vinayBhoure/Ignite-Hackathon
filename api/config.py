"""Env-driven settings for api/main.py. Fails fast at startup, not deep in a request.

CLAUDE.md: any new variable must also be added to .env.example.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    use_mocks: bool = field(default_factory=lambda: _bool_env("USE_MOCKS", True))

    neo4j_uri: str | None = field(default_factory=lambda: os.getenv("NEO4J_URI"))
    neo4j_username: str | None = field(default_factory=lambda: os.getenv("NEO4J_USERNAME"))
    neo4j_password: str | None = field(default_factory=lambda: os.getenv("NEO4J_PASSWORD"))

    # Falls back to the single GOOGLE_MAPS_API_KEY the .env currently has if the
    # split server/browser keys CLAUDE.md calls for aren't set yet (TODO T2.7:
    # get a referrer-restricted browser key so it's safe to ship to the client).
    google_maps_server_key: str | None = field(
        default_factory=lambda: os.getenv("GOOGLE_MAPS_SERVER_KEY") or os.getenv("GOOGLE_MAPS_API_KEY")
    )
    google_maps_browser_key: str | None = field(
        default_factory=lambda: os.getenv("GOOGLE_MAPS_BROWSER_KEY") or os.getenv("GOOGLE_MAPS_API_KEY")
    )
    gemini_api_key: str | None = field(default_factory=lambda: os.getenv("GEMINI_API_KEY"))

    vapid_public_key: str | None = field(default_factory=lambda: os.getenv("VAPID_PUBLIC_KEY"))
    vapid_private_key: str | None = field(default_factory=lambda: os.getenv("VAPID_PRIVATE_KEY"))
    vapid_subject: str | None = field(default_factory=lambda: os.getenv("VAPID_SUBJECT"))

    demo_area_bounds: str | None = field(default_factory=lambda: os.getenv("DEMO_AREA_BOUNDS"))
    h3_res: int = field(default_factory=lambda: int(os.getenv("H3_RES", "8")))
    sensor_radius_km: float = field(
        default_factory=lambda: float(os.getenv("SENSOR_RADIUS_KM", "3"))
    )

    cors_origins: list[str] = field(
        default_factory=lambda: [
            o.strip()
            for o in os.getenv("CORS_ORIGINS", "*").split(",")
            if o.strip()
        ]
    )

    # The two front doors link to each other: the login page (API) hands the
    # dispatcher off to the console, and the console links back to sign out.
    public_api_url: str = field(
        default_factory=lambda: os.getenv("PUBLIC_API_URL", "http://127.0.0.1:8010").rstrip("/")
    )
    console_url: str = field(
        default_factory=lambda: os.getenv("CONSOLE_URL", "http://127.0.0.1:8501").rstrip("/")
    )

    def validate(self) -> None:
        """Raise a clear RuntimeError for missing config, called once at startup."""
        missing: list[str] = []

        if not self.neo4j_uri or not self.neo4j_username or not self.neo4j_password:
            missing.append("NEO4J_URI/NEO4J_USERNAME/NEO4J_PASSWORD")

        if not self.use_mocks:
            # Gemini is optional: without it, route explanations fall back to a
            # template sentence built from the same graph numbers.
            if not self.google_maps_server_key:
                missing.append("GOOGLE_MAPS_SERVER_KEY (required when USE_MOCKS=false)")
            if not (self.vapid_public_key and self.vapid_private_key and self.vapid_subject):
                missing.append("VAPID_PUBLIC_KEY/VAPID_PRIVATE_KEY/VAPID_SUBJECT")

        if missing:
            raise RuntimeError(
                "Missing required environment variables: " + "; ".join(missing) +
                ". Copy .env.example to .env and fill them in."
            )


def get_settings() -> Settings:
    return Settings()
