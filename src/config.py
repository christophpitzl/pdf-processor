"""
Centralized configuration for PDF Processor.

All defaults are defined here — override via environment variables or a .env file.
This is the single source of truth for every configurable parameter.
"""

from dataclasses import dataclass
from typing import Optional
import os


@dataclass
class Settings:
    """Application settings with sensible defaults.

    Create an instance via ``Settings.from_env()`` to load overrides
    from environment variables (and a ``.env`` file if present).
    """

    # ── NFS ─────────────────────────────────────────────────────────────
    nfs_watch_dir: str = "/mnt/nfs/incoming"
    nfs_output_dir: str = "/mnt/nfs/processed"
    nfs_server: Optional[str] = None
    nfs_export_path: Optional[str] = None
    nfs_mount_options: str = "hard,intr,noatime"

    # ── Ollama ──────────────────────────────────────────────────────────
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "granite4.1:3b"

    # ── Wake-on-LAN ─────────────────────────────────────────────────────
    ollama_wol_enabled: bool = False
    ollama_mac_address: Optional[str] = None
    ollama_broadcast_host: str = "255.255.255.255"
    ollama_wol_port: int = 9
    ollama_wol_retries: int = 10
    ollama_wol_retry_delay: float = 5.0

    # ── PDF processing ──────────────────────────────────────────────────
    scan_date_format: str = "%Y-%m-%d"
    min_confidence: float = 0.6
    filename_pattern: str = "{date}_{type}_{summary}.pdf"
    check_interval: int = 60

    # ── Web interface ───────────────────────────────────────────────────
    web_host: str = "0.0.0.0"
    web_port: int = 8080

    # ── Paths ───────────────────────────────────────────────────────────
    data_dir: str = "./data"
    logs_dir: str = "./logs"

    # ── Logging ─────────────────────────────────────────────────────────
    log_level: str = "INFO"

    # ── Public methods ──────────────────────────────────────────────────

    @classmethod
    def from_env(cls) -> "Settings":
        """Build a ``Settings`` from environment variables (and ``.env``).

        Every field can be overridden through its corresponding environment
        variable.  Only the fields listed below are read — unknown variables
        are silently ignored.
        """
        return cls(
            # NFS
            nfs_watch_dir=os.getenv("NFS_WATCH_DIR", "/mnt/nfs/incoming"),
            nfs_output_dir=os.getenv("NFS_OUTPUT_DIR", "/mnt/nfs/processed"),
            nfs_server=os.getenv("NFS_SERVER"),
            nfs_export_path=os.getenv("NFS_EXPORT_PATH"),
            nfs_mount_options=os.getenv("NFS_MOUNT_OPTIONS", "hard,intr,noatime"),
            # Ollama
            ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            ollama_model=os.getenv("OLLAMA_MODEL", "granite4.1:3b"),
            # WOL
            ollama_wol_enabled=os.getenv("OLLAMA_WOL_ENABLED", "false").lower()
            == "true",
            ollama_mac_address=os.getenv("OLLAMA_MAC_ADDRESS"),
            ollama_broadcast_host=os.getenv("OLLAMA_BROADCAST_HOST", "255.255.255.255"),
            ollama_wol_port=int(os.getenv("OLLAMA_WOL_PORT", "9")),
            ollama_wol_retries=int(os.getenv("OLLAMA_WOL_RETRIES", "10")),
            ollama_wol_retry_delay=float(os.getenv("OLLAMA_WOL_RETRY_DELAY", "5.0")),
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
            # Paths
            data_dir=os.getenv("DATA_DIR", "./data"),
            logs_dir=os.getenv("LOGS_DIR", "./logs"),
            # Logging
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )
