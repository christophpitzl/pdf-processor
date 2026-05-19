"""
Web interface for PDF Processor.
Provides a web UI to monitor status and trigger manual processing.
"""

import os
import threading
import time
from pathlib import Path
from typing import Dict, Any, Optional

from webdav3.exceptions import WebDavException

from flask import Flask, render_template, jsonify, request
from loguru import logger
import httpx

from src.main import PDFProcessor


class WebApp:
    """Flask web application for PDF Processor."""
    
    def __init__(self, processor: PDFProcessor):
        """Initialize web app with processor instance."""
        self.processor = processor
        self.app = Flask(__name__, template_folder=str(Path(__file__).parent / 'templates'))
        self._setup_routes()
        self._processing = False
        self._processing_thread: Optional[threading.Thread] = None
        
    def _setup_routes(self):
        """Setup Flask routes."""
        self.app.route('/')(self.index)
        self.app.route('/api/status')(self.api_status)
        self.app.route('/api/process', methods=['POST'])(self.api_process)
        self.app.route('/api/diagnostics')(self.api_diagnostics)
        
    def index(self):
        """Render main page."""
        return render_template('index.html')
    
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
            return jsonify({"status": "already_running", "message": "Processing already in progress"}), 409
        
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
                # Check if there are files to process
                if not self.processor.webdav_client:
                    logger.error("WebDAV client not initialized")
                    break
                
                files = self.processor.webdav_client.list(self.processor.watch_folder)
                # webdavclient3 list() returns a list of strings (filenames) or None
                if files is None:
                    pdf_files = []
                else:
                    pdf_files = [
                        f for f in files 
                        if isinstance(f, str) and f.endswith('.pdf')
                    ]
                
                if not pdf_files:
                    logger.info("Input folder is empty, stopping manual processing")
                    break
                
                logger.info(f"Found {len(pdf_files)} files to process")
                self.processor.check_for_new_files()
                
                # Small delay to avoid tight loop
                time.sleep(1)
        except Exception as e:
            logger.error(f"Error in manual processing: {e}")
        finally:
            self._processing = False
            logger.info("Manual processing finished")
    
    def _get_status(self) -> Dict[str, Any]:
        """Get current processing status."""
        status = {
            "input_count": 0,
            "output_count": 0,
            "processing": self._processing,
            "check_interval": self.processor.check_interval,
            "folders": self._check_folders(),
        }
        
        try:
            if self.processor.webdav_client:
                # Count input files
                files = self.processor.webdav_client.list(self.processor.watch_folder)
                # webdavclient3 list() returns a list of strings (filenames) or None
                if files is None:
                    pdf_files = []
                else:
                    pdf_files = [
                        f for f in files 
                        if isinstance(f, str) and f.endswith('.pdf')
                    ]
                status["input_count"] = len(pdf_files)
                
                # Count output files
                try:
                    output_files = self.processor.webdav_client.list(self.processor.output_folder)
                    # webdavclient3 list() returns a list of strings (filenames) or None
                    if output_files is None:
                        output_pdfs = []
                    else:
                        output_pdfs = [
                            f for f in output_files 
                            if isinstance(f, str) and f.endswith('.pdf')
                        ]
                    status["output_count"] = len(output_pdfs)
                except Exception as e:
                    logger.debug(f"Could not list output folder: {e}")
                    status["output_count"] = -1  # Indicates error
        except Exception as e:
            logger.error(f"Error getting status: {e}")
        
        return status

    def _check_folders(self) -> Dict[str, Any]:
        """Check status of input/output folders.

        Returns:
            Dictionary with folder status information including existence,
            readability, and file counts.
        """
        folders_status = {
            "data_dir": self._check_local_folder(self.processor.data_dir, "local"),
            "logs_dir": self._check_local_folder(self.processor.logs_dir, "local"),
            "watch_folder": self._check_webdav_folder(self.processor.watch_folder, "webdav"),
            "output_folder": self._check_webdav_folder(self.processor.output_folder, "webdav"),
        }
        return folders_status

    def _check_local_folder(self, path_str: str, folder_type: str) -> Dict[str, Any]:
        """Check a local filesystem folder.

        Args:
            path_str: Path to the folder.
            folder_type: Type label for logging (e.g., "local").

        Returns:
            Dictionary with status information.
        """
        path = Path(path_str)
        status = {
            "path": str(path),
            "type": folder_type,
            "exists": False,
            "is_directory": False,
            "readable": False,
            "writable": False,
            "error": None,
        }

        try:
            if not path.exists():
                status["error"] = "Folder does not exist"
                logger.warning(f"Local folder does not exist: {path}")
                return status

            status["exists"] = True

            if not path.is_dir():
                status["error"] = "Path exists but is not a directory"
                logger.error(f"Local path is not a directory: {path}")
                return status

            status["is_directory"] = True

            # Check readability
            if os.access(str(path), os.R_OK):
                status["readable"] = True
            else:
                status["error"] = "Folder is not readable"
                logger.error(f"Local folder not readable: {path}")

            # Check writability
            if os.access(str(path), os.W_OK):
                status["writable"] = True
            else:
                status["error"] = status.get("error") or "Folder is not writable"
                logger.error(f"Local folder not writable: {path}")

        except PermissionError:
            status["error"] = "Permission denied"
            logger.error(f"Permission denied accessing local folder: {path}")
        except Exception as e:
            status["error"] = str(e)
            logger.error(f"Error checking local folder {path}: {e}")

        return status

    def _check_webdav_folder(self, folder_path: str, folder_type: str) -> Dict[str, Any]:
        """Check a WebDAV folder.

        Args:
            folder_path: WebDAV folder path.
            folder_type: Type label for logging (e.g., "webdav").

        Returns:
            Dictionary with status information.
        """
        status = {
            "path": folder_path,
            "type": folder_type,
            "exists": False,
            "readable": False,
            "file_count": 0,
            "error": None,
        }

        if not self.processor.webdav_client:
            status["error"] = "WebDAV client not initialized"
            logger.error("Cannot check WebDAV folder: client not initialized")
            return status

        try:
            # Try to list contents — if it succeeds the folder exists
            # and is readable.  We deliberately skip webdav_client.check()
            # because many NAS WebDAV servers (Synology, QNAP, etc.) return
            # false negatives for check() even though the folder is perfectly
            # accessible.
            files = self.processor.webdav_client.list(folder_path)
            status["exists"] = True
            status["readable"] = True
            status["file_count"] = len(files) if files else 0

        except WebDavException as e:
            status["error"] = f"WebDAV error: {e}"
            logger.error(f"WebDAV error checking folder {folder_path}: {e}")
        except Exception as e:
            status["error"] = str(e)
            logger.error(f"Error checking WebDAV folder {folder_path}: {e}")

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
            "webdav": self._diagnose_webdav(),
            "folders": self._check_folders(),
            "configuration": self._diagnose_configuration(),
        }
        return diagnostics

    def _diagnose_ollama(self) -> Dict[str, Any]:
        """Check Ollama connectivity and model availability."""
        result = {
            "base_url": self.processor.ollama_base_url,
            "model": self.processor.ollama_model,
            "reachable": False,
            "model_available": False,
            "error": None,
        }
        try:
            r = httpx.get(
                f"{self.processor.ollama_base_url}/api/tags",
                timeout=5.0,
            )
            if r.status_code == 200:
                result["reachable"] = True
                models = r.json().get("models", [])
                available_models = [m["name"] for m in models]
                result["available_models"] = available_models
                # Check if configured model is in the list (Ollama may return
                # tags like "granite4.1:3b" or "granite4.1:3b (some variant)")
                configured = self.processor.ollama_model
                result["model_available"] = any(
                    configured in m for m in available_models
                )
            else:
                result["error"] = f"HTTP {r.status_code}: {r.text[:200]}"
        except httpx.ConnectError as e:
            result["error"] = f"Connection refused: {e}"
        except httpx.TimeoutException as e:
            result["error"] = f"Connection timed out: {e}"
        except Exception as e:
            result["error"] = str(e)
        return result

    def _diagnose_webdav(self) -> Dict[str, Any]:
        """Check WebDAV connectivity and folder accessibility."""
        result = {
            "url": self.processor.webdav_url,
            "connected": False,
            "error": None,
        }
        if not self.processor.webdav_client:
            result["error"] = "WebDAV client not initialized"
            return result

        try:
            # Quick connectivity probe: try to list root
            root_list = self.processor.webdav_client.list("/")
            result["connected"] = True
            result["root_contents"] = (
                [str(f) for f in root_list] if root_list else []
            )
        except WebDavException as e:
            result["error"] = f"WebDAV error: {e}"
        except Exception as e:
            result["error"] = str(e)
        return result

    def _diagnose_configuration(self) -> Dict[str, Any]:
        """Return sanitised configuration values for debugging."""
        s = self.processor.settings
        return {
            "ollama_base_url": s.ollama_base_url,
            "ollama_model": s.ollama_model,
            "ollama_wol_enabled": s.ollama_wol_enabled,
            "webdav_url": s.webdav_url,
            "webdav_watch_folder": s.webdav_watch_folder,
            "webdav_output_folder": s.webdav_output_folder,
            "check_interval": s.check_interval,
            "scan_date_format": s.scan_date_format,
            "min_confidence": s.min_confidence,
            "filename_pattern": s.filename_pattern,
            "data_dir": s.data_dir,
            "logs_dir": s.logs_dir,
            "web_host": s.web_host,
            "web_port": s.web_port,
            "log_level": s.log_level,
            "ollama_username_configured": (
                s.webdav_username is not None
            ),
            "ollama_password_configured": (
                s.webdav_password is not None
            ),
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
