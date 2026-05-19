"""
Web interface for PDF Processor.
Provides a web UI to monitor status and trigger manual processing.
"""

import threading
import time
from pathlib import Path
from typing import Dict, Any, Optional

from flask import Flask, render_template, jsonify, request
from loguru import logger

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
            if not self.processor.webdav_client.check(folder_path):
                status["error"] = "Folder does not exist on WebDAV"
                logger.warning(f"WebDAV folder does not exist: {folder_path}")
                return status

            status["exists"] = True

            # Try to list contents to verify readability
            files = self.processor.webdav_client.list(folder_path)
            status["readable"] = True
            status["file_count"] = len(files)

        except WebDavException as e:
            status["error"] = f"WebDAV error: {e}"
            logger.error(f"WebDAV error checking folder {folder_path}: {e}")
        except Exception as e:
            status["error"] = str(e)
            logger.error(f"Error checking WebDAV folder {folder_path}: {e}")

        return status

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
