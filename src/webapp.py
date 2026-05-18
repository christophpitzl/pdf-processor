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
                # webdavclient3 list() returns a list of strings (filenames)
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
        }
        
        try:
            if self.processor.webdav_client:
                # Count input files
                files = self.processor.webdav_client.list(self.processor.watch_folder)
                # webdavclient3 list() returns a list of strings (filenames)
                pdf_files = [
                    f for f in files 
                    if isinstance(f, str) and f.endswith('.pdf')
                ]
                status["input_count"] = len(pdf_files)
                
                # Count output files
                try:
                    output_files = self.processor.webdav_client.list(self.processor.output_folder)
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
