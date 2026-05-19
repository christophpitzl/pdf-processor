"""
Web interface for PDF Processor.
Provides a web UI to monitor status and trigger manual processing.
"""

import os
import threading
import time
from pathlib import Path
from typing import Dict, Any, Optional, List

from flask import Flask, render_template, jsonify
from loguru import logger
import httpx

from src.main import PDFProcessor


class WebApp:
    """Flask web application for PDF Processor."""

    def __init__(self, processor: PDFProcessor):
        """Initialize web app with processor instance."""
        self.processor = processor
        self.app = Flask(
            __name__,
            template_folder=str(Path(__file__).parent / "templates"),
        )
        self._setup_routes()
        self._processing = False
        self._processing_thread: Optional[threading.Thread] = None

    def _setup_routes(self):
        """Setup Flask routes."""
        self.app.route("/")(self.index)
        self.app.route("/api/status")(self.api_status)
        self.app.route("/api/process", methods=["POST"])(self.api_process)
        self.app.route("/api/diagnostics")(self.api_diagnostics)

    def index(self):
        """Render main page."""
        return render_template("index.html")

    def api_status(self):
        """Return current status as JSON."""
        try:
            status = self._get_status()
            return jsonify(status)
        except Exception as e:
            logger.error(f"Error getting status: {e}")
            return jsonify({"error": str(e)}), 500

    def api_process(self):
        """Trigger manual processing."""
        if self._processing:
            return (
                jsonify(
                    {
                        "status": "already_running",
                        "message": "Processing already in progress",
                    }
                ),
                409,
            )

        # Start processing in background thread
        self._processing_thread = threading.Thread(target=self._process_until_empty)
        self._processing_thread.daemon = True
        self._processing_thread.start()

        return jsonify({"status": "started", "message": "Processing started"})

    def _process_until_empty(self):
        """Process files until input folder is empty."""
        self._processing = True
        try:
            logger.info("Manual processing started")
            while True:
                watch_dir = self.processor.watch_dir.resolve()
                if not watch_dir.exists():
                    logger.error("Watch directory does not exist: " f"{watch_dir}")
                    break

                pdf_files: List[Path] = sorted(
                    [
                        f
                        for f in watch_dir.iterdir()
                        if f.is_file() and f.suffix.lower() == ".pdf"
                    ],
                    key=lambda p: p.stat().st_mtime,
                )

                if not pdf_files:
                    logger.info("Input folder is empty, stopping manual processing")
                    break

                logger.info(f"Found {len(pdf_files)} file(s) to process")
                self.processor.check_for_new_files()

                time.sleep(1)
        except Exception as e:
            logger.error(f"Error in manual processing: {e}")
        finally:
            self._processing = False
            logger.info("Manual processing finished")

    def _count_pdfs(self, directory: Path) -> int:
        """Count PDF files in a directory (flat, non-recursive).

        Returns -1 if the directory cannot be accessed.
        """
        try:
            if not directory.exists():
                return 0
            return len(
                [
                    f
                    for f in directory.iterdir()
                    if f.is_file() and f.suffix.lower() == ".pdf"
                ]
            )
        except Exception as e:
            logger.debug(f"Could not list directory {directory}: {e}")
            return -1

    def _get_status(self) -> Dict[str, Any]:
        """Get current processing status."""
        status = {
            "input_count": 0,
            "output_count": 0,
            "processing": self._processing,
            "check_interval": self.processor.check_interval,
            "folders": self._check_folders(),
        }

        input_dir = self.processor.watch_dir.resolve()
        output_dir = self.processor.output_dir.resolve()

        status["input_count"] = self._count_pdfs(input_dir)

        is_error = False
        out_count = self._count_pdfs(output_dir)
        if out_count < 0:
            is_error = True
            status["output_folder_error"] = (
                f"Error listing output directory: {output_dir}"
            )
        status["output_count"] = -1 if is_error else out_count

        return status

    def _check_folders(self) -> Dict[str, Any]:
        """Check status of input/output folders.

        Returns:
            Dictionary with folder status information.
        """
        folders_status = {
            "data_dir": self._check_local_folder(self.processor.data_dir, "local"),
            "logs_dir": self._check_local_folder(self.processor.logs_dir, "local"),
            "watch_dir": self._check_local_folder(str(self.processor.watch_dir), "host"),
            "output_dir": self._check_local_folder(
                str(self.processor.output_dir), "host"
            ),
        }
        return folders_status

    def _check_local_folder(self, path_str: str, folder_type: str) -> Dict[str, Any]:
        """Check a filesystem folder.

        Args:
            path_str: Path to the folder.
            folder_type: Type label ("local" or "host").

        Returns:
            Dictionary with status information.
        """
        path = Path(path_str)
        status: Dict[str, Any] = {
            "path": str(path),
            "type": folder_type,
            "exists": False,
            "is_directory": False,
            "readable": False,
            "writable": False,
            "file_count": 0,
            "error": None,
        }

        try:
            if not path.exists():
                status["error"] = "Folder does not exist"
                if folder_type == "host":
                    status["hint"] = (
                        "Make sure this folder is mapped as a Docker volume "
                        "in docker-compose.yml."
                    )
                logger.warning(f"Folder does not exist: {path}")
                return status

            status["exists"] = True

            if not path.is_dir():
                status["error"] = "Path exists but is not a directory"
                logger.error(f"Path is not a directory: {path}")
                return status

            status["is_directory"] = True

            # Count items
            try:
                items = list(path.iterdir())
                status["file_count"] = len(items)
            except Exception:
                status["file_count"] = -1

            # Check readability
            if os.access(str(path), os.R_OK):
                status["readable"] = True
            else:
                status["error"] = "Folder is not readable"

            # Write test
            try:
                test_file = path / ".write_test_tmp"
                test_file.write_text("ok")
                test_file.unlink()
                status["writable"] = True
            except Exception as we:
                status["writable"] = False
                msg = f"Write test failed: {we}"
                status["error"] = status.get("error") or msg
                logger.debug(f"Write test failed for {path}: {we}")

        except PermissionError:
            status["error"] = "Permission denied"
            logger.error(f"Permission denied accessing folder: {path}")
        except Exception as e:
            status["error"] = str(e)
            logger.error(f"Error checking folder {path}: {e}")

        return status

    def api_diagnostics(self):
        """Run comprehensive diagnostics and return results as JSON."""
        try:
            results = self._run_diagnostics()
            return jsonify(results)
        except Exception as e:
            logger.error(f"Error running diagnostics: {e}")
            return jsonify({"error": str(e)}), 500

    def _run_diagnostics(self) -> Dict[str, Any]:
        """Run all diagnostic checks and return structured results."""
        diagnostics = {
            "ollama": self._diagnose_ollama(),
            "folders": self._diagnose_folders(),
            "folder_details": self._check_folders(),
            "configuration": self._diagnose_configuration(),
        }
        return diagnostics

    def _diagnose_folders(self) -> Dict[str, Any]:
        """Check incoming/processed folder accessibility."""
        result: Dict[str, Any] = {
            "incoming_dir": str(self.processor.watch_dir),
            "processed_dir": str(self.processor.output_dir),
            "incoming_exists": False,
            "processed_exists": False,
            "error": None,
        }

        watch = self.processor.watch_dir.resolve()
        output = self.processor.output_dir.resolve()

        result["incoming_exists"] = watch.exists()
        result["processed_exists"] = output.exists()

        # List contents if they exist
        if watch.exists():
            try:
                children = sorted([p.name for p in watch.iterdir()])
                result["incoming_contents"] = children
            except Exception as e:
                result["incoming_list_error"] = str(e)

        if output.exists():
            try:
                children = sorted([p.name for p in output.iterdir()])
                result["processed_contents"] = children
            except Exception as e:
                result["processed_list_error"] = str(e)

        return result

    def _diagnose_configuration(self) -> Dict[str, Any]:
        """Return sanitised configuration values for debugging."""
        s = self.processor.settings
        return {
            "ollama_base_url": s.ollama_base_url,
            "ollama_model": s.ollama_model,
            "ollama_wol_enabled": s.ollama_wol_enabled,
            "incoming_dir": s.incoming_dir,
            "processed_dir": s.processed_dir,
            "check_interval": s.check_interval,
            "scan_date_format": s.scan_date_format,
            "min_confidence": s.min_confidence,
            "filename_pattern": s.filename_pattern,
            "data_dir": s.data_dir,
            "logs_dir": s.logs_dir,
            "web_host": s.web_host,
            "web_port": s.web_port,
            "log_level": s.log_level,
        }

    def run(self, host=None, port=None, debug=False):
        """Run the Flask app.

        Args:
            host: Host to bind to.  Falls back to ``settings.web_host``.
            port: Port to bind to.  Falls back to ``settings.web_port``.
            debug: Enable Flask debug mode.
        """
        host = host or self.processor.settings.web_host
        port = port or self.processor.settings.web_port
        self.app.run(host=host, port=port, debug=debug, threaded=True)


def create_app(processor: PDFProcessor) -> Flask:
    """Create and return Flask app."""
    webapp = WebApp(processor)
    return webapp.app
