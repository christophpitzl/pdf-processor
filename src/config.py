"""
Centralized configuration for PDF Processor.

All defaults are defined here — override via environment variables or a .env file.
This is the single source of truth for every configurable parameter.
"""

from dataclasses import dataclass
import os


@dataclass
class Settings:
    """Application settings with sensible defaults.

    Create an instance via ``Settings.from_env()`` to load overrides
    from environment variables (and a ``.env`` file if present).

    The ``incoming_dir`` and ``processed_dir`` point to host-mounted
    volumes at ``/incoming`` and ``/processed`` inside the container.
    Configure these via ``docker-compose.yml`` volume mappings.
    """

    # ── Host-mounted directories ────────────────────────────────────────
    incoming_dir: str = "/incoming"
    processed_dir: str = "/processed"

    # ── Ollama ──────────────────────────────────────────────────────────
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "granite4.1:3b"

    # ── PDF processing ──────────────────────────────────────────────────
    scan_date_format: str = "%Y-%m-%d"
    min_confidence: float = 0.6
    filename_pattern: str = "{date}_{type}_{summary}.pdf"
    check_interval: int = 60

    # ── Web interface ───────────────────────────────────────────────────
    web_host: str = "0.0.0.0"
    web_port: int = 8080

    # ── Internal container paths (hardcoded) ────────────────────────────
    data_dir: str = "/app/data"
    logs_dir: str = "/app/logs"

    # ── Logging ─────────────────────────────────────────────────────────
    log_level: str = "INFO"

    # ── Language ──────────────────────────────────────────────────────
    language: str = "de"

    @classmethod
    def from_env(cls) -> "Settings":
        """Build a ``Settings`` from environment variables (and ``.env``).

        Every field can be overridden through its corresponding environment
        variable.  Only the fields listed below are read — unknown variables
        are silently ignored.
        """
        return cls(
            # Host-mounted directories (hardcoded defaults)
            incoming_dir="/incoming",
            processed_dir="/processed",
            # Ollama
            ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            ollama_model=os.getenv("OLLAMA_MODEL", "granite4.1:3b"),
            # Processing
            scan_date_format=os.getenv("SCAN_DATE_FORMAT", "%Y-%m-%d"),
            min_confidence=float(os.getenv("MIN_CONFIDENCE", "0.6")),
            filename_pattern=os.getenv(
                "FILENAME_PATTERN", "{date}_{type}_{summary}.pdf"
            ),
            check_interval=int(os.getenv("CHECK_INTERVAL", "60")),
            # Web
            web_host=os.getenv("WEB_HOST", "0.0.0.0"),
            web_port=int(os.getenv("WEB_PORT", "8080")),
            # Logging
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            # Language
            language=os.getenv("LANGUAGE", "de"),
        )
