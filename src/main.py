"""
PDF Processor - Main Application
Monitors WebDAV folder, processes PDF files with local AI (Ollama), and renames them based on content.
"""

import os
import re
import time
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
from loguru import logger
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# WebDAV client
from webdav3.client import Client
from webdav3.exceptions import WebDavException

# PDF processing
from PyPDF2 import PdfReader
import pdfplumber

# HTTP client for Ollama API
import httpx

# WOL (Wake-on-LAN) for waking up Ollama server
from src.utils.wol import wake_on_lan, wait_for_ollama

# Centralized configuration
from src.config import Settings


class PDFProcessor:
    """Main class for processing PDF files from WebDAV."""

    def __init__(self, settings: Optional[Settings] = None):
        """Initialize the PDF processor with configuration.

        Args:
            settings: A ``Settings`` instance.  When ``None`` the settings
                      are loaded from environment variables automatically.
        """
        self.settings = settings if settings is not None else Settings.from_env()
        s = self.settings  # short alias for convenience

        self.webdav_url = s.webdav_url
        self.webdav_username = s.webdav_username
        self.webdav_password = s.webdav_password
        self.watch_folder = s.webdav_watch_folder
        self.output_folder = s.webdav_output_folder
        self.ollama_base_url = s.ollama_base_url
        self.ollama_model = s.ollama_model
        self.ollama_mac_address = s.ollama_mac_address
        self.ollama_broadcast_host = s.ollama_broadcast_host
        self.ollama_wol_port = s.ollama_wol_port
        self.ollama_wol_enabled = s.ollama_wol_enabled
        self.ollama_wol_retries = s.ollama_wol_retries
        self.ollama_wol_retry_delay = s.ollama_wol_retry_delay
        self.scan_date_format = s.scan_date_format
        self.min_confidence = s.min_confidence
        self.filename_pattern = s.filename_pattern
        self.check_interval = s.check_interval
        self.log_level = s.log_level
        self.data_dir = s.data_dir
        self.logs_dir = s.logs_dir

        # Setup logging
        logger.remove()
        logger.add(
            Path(self.logs_dir) / "pdf-processor.log",
            level=self.log_level,
            rotation="10 MB",
            retention="30 days",
        )
        logger.add(lambda msg: print(msg, end=""), level=self.log_level)

        # Initialize WebDAV client
        self.webdav_client = self._init_webdav_client()

        # Initialize Ollama HTTP client
        self.ollama_client = httpx.Client(
            base_url=self.ollama_base_url,
            timeout=httpx.Timeout(120.0, connect=10.0),
        )

        # Track processed files to avoid duplicates
        self.processed_files: Dict[str, str] = {}

        # Validate local directories
        self._validate_local_directories()

        # Validate WebDAV connection and folders
        self._validate_webdav_folders()

        # Wake up Ollama server via WOL if enabled
        if self.ollama_wol_enabled and self.ollama_mac_address:
            logger.info("WOL enabled, waking up Ollama server...")
            wake_on_lan(
                self.ollama_mac_address,
                host=self.ollama_broadcast_host,
                port=self.ollama_wol_port,
            )
            if not wait_for_ollama(
                ollama_base_url=self.ollama_base_url,
                ollama_model=self.ollama_model,
                max_retries=self.ollama_wol_retries,
                retry_delay=self.ollama_wol_retry_delay,
            ):
                logger.warning(
                    "Ollama server did not become ready, "
                    "processing may fail if Ollama is not already running"
                )
        elif self.ollama_wol_enabled and not self.ollama_mac_address:
            logger.warning(
                "OLLAMA_WOL_ENABLED=true but OLLAMA_MAC_ADDRESS not set, "
                "skipping WOL wake-up"
            )
        else:
            logger.debug("WOL not enabled, skipping Ollama wake-up")

    def _init_webdav_client(self) -> Optional[Client]:
        """Initialize and return WebDAV client."""
        if not self.webdav_username or not self.webdav_password:
            logger.error("WebDAV credentials not provided")
            return None

        options = {
            "webdav_hostname": self.webdav_url,
            "webdav_login": self.webdav_username,
            "webdav_password": self.webdav_password,
            "webdav_timeout": 60,
        }

        try:
            client = Client(options)
            client.verify = False  # Disable SSL verification for self-signed certs
            logger.info("WebDAV client initialized")
            return client
        except Exception as e:
            logger.error(f"Failed to initialize WebDAV client: {e}")
            return None

    def _validate_local_directories(self) -> None:
        """Validate and create local directories if needed."""
        data_path = Path(self.data_dir)
        logs_path = Path(self.logs_dir)

        # Check and create data directory
        try:
            if not data_path.exists():
                logger.warning(f"Data directory does not exist: {data_path}")
                data_path.mkdir(parents=True, exist_ok=True)
                logger.info(f"Created data directory: {data_path}")
            elif not data_path.is_dir():
                logger.error(f"Data path exists but is not a directory: {data_path}")
            elif not os.access(str(data_path), os.R_OK | os.W_OK):
                logger.error(f"Data directory is not readable/writable: {data_path}")
            else:
                logger.debug(f"Data directory validated: {data_path}")
        except PermissionError:
            logger.error(f"Permission denied accessing data directory: {data_path}")
        except Exception as e:
            logger.error(f"Error validating data directory {data_path}: {e}")

        # Check and create logs directory
        try:
            if not logs_path.exists():
                logger.warning(f"Logs directory does not exist: {logs_path}")
                logs_path.mkdir(parents=True, exist_ok=True)
                logger.info(f"Created logs directory: {logs_path}")
            elif not logs_path.is_dir():
                logger.error(f"Logs path exists but is not a directory: {logs_path}")
            elif not os.access(str(logs_path), os.R_OK | os.W_OK):
                logger.error(f"Logs directory is not readable/writable: {logs_path}")
            else:
                logger.debug(f"Logs directory validated: {logs_path}")
        except PermissionError:
            logger.error(f"Permission denied accessing logs directory: {logs_path}")
        except Exception as e:
            logger.error(f"Error validating logs directory {logs_path}: {e}")

    def _validate_webdav_folders(self) -> None:
        """Validate WebDAV connection and check if folders exist and are accessible."""
        if not self.webdav_client:
            logger.error("Cannot validate WebDAV folders: client not initialized")
            return

        # Check watch folder
        try:
            logger.info(f"Checking WebDAV watch folder: {self.watch_folder}")
            if self.webdav_client.check(self.watch_folder):
                # Try to list contents to verify readability
                files = self.webdav_client.list(self.watch_folder)
                logger.info(f"Watch folder accessible: {self.watch_folder} ({len(files)} items)")
            else:
                logger.warning(f"Watch folder does not exist on WebDAV: {self.watch_folder}")
                # Attempt to create it
                try:
                    self.webdav_client.mkdir(self.watch_folder)
                    logger.info(f"Created watch folder on WebDAV: {self.watch_folder}")
                except Exception as e:
                    logger.error(f"Failed to create watch folder {self.watch_folder}: {e}")
        except WebDavException as e:
            logger.error(f"WebDAV error accessing watch folder {self.watch_folder}: {e}")
        except Exception as e:
            logger.error(f"Error validating watch folder {self.watch_folder}: {e}")

        # Check output folder
        try:
            logger.info(f"Checking WebDAV output folder: {self.output_folder}")
            if self.webdav_client.check(self.output_folder):
                files = self.webdav_client.list(self.output_folder)
                logger.info(f"Output folder accessible: {self.output_folder} ({len(files)} items)")
            else:
                logger.warning(f"Output folder does not exist on WebDAV: {self.output_folder}")
                try:
                    self.webdav_client.mkdir(self.output_folder)
                    logger.info(f"Created output folder on WebDAV: {self.output_folder}")
                except Exception as e:
                    logger.error(f"Failed to create output folder {self.output_folder}: {e}")
        except WebDavException as e:
            logger.error(f"WebDAV error accessing output folder {self.output_folder}: {e}")
        except Exception as e:
            logger.error(f"Error validating output folder {self.output_folder}: {e}")

    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """Extract text from PDF file using multiple methods."""
        text = ""

        try:
            # Method 1: Use pdfplumber for better text extraction
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"

            # If text extraction failed, try PyPDF2
            if not text.strip():
                reader = PdfReader(pdf_path)
                for page in reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"

            logger.debug(f"Extracted {len(text)} characters from PDF")
            return text.strip()

        except Exception as e:
            logger.error(f"Error extracting text from PDF: {e}")
            return ""

    def analyze_document_with_ai(self, text: str) -> Dict[str, Any]:
        """Analyze document content using a local Ollama model."""
        if not text:
            logger.warning("No text to analyze")
            return {}

        # Create prompt for document analysis
        prompt = f"""Analyze the following document text and extract key information.

Return a JSON object with the following structure:
{{
    "document_type": "invoice|receipt|contract|letter|report|other",
    "date": "YYYY-MM-DD format if found, otherwise null",
    "summary": "brief 2-4 word summary of the document content",
    "confidence": 0.0-1.0 confidence score",
    "entities": ["list of important entities like company names, person names, etc."]
}}

Document text:
{text[:4000]}  # Limit text length for API

Only return valid JSON, no additional text."""

        try:
            response = self.ollama_client.post(
                "/api/chat",
                json={
                    "model": self.ollama_model,
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a document analysis assistant. Always return valid JSON.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "stream": False,
                    "options": {"temperature": 0.3, "num_predict": 500},
                },
            )
            response.raise_for_status()

            content = response.json()["message"]["content"].strip()

            # Try to parse JSON from the response
            try:
                # Try to find JSON in the response
                json_start = content.find("{")
                json_end = content.rfind("}") + 1
                if json_start != -1 and json_end > json_start:
                    content = content[json_start:json_end]
                result = json.loads(content)
                return result
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse Ollama response as JSON: {e}")
                logger.debug(f"Response content: {content}")
                return {}

        except httpx.RequestError as e:
            logger.error(
                f"Error calling Ollama API at {self.ollama_base_url}: {e}. "
                f"Make sure Ollama is running and the model '{self.ollama_model}' is pulled."
            )
            return {}
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            logger.error(f"Error parsing Ollama response: {e}")
            return {}

    def generate_filename(self, analysis: Dict[str, Any], original_filename: str) -> str:
        """Generate new filename based on analysis and pattern."""
        if not analysis:
            return original_filename

        # Extract date from analysis or use current date
        date_str = ""
        if analysis.get("date"):
            try:
                date_obj = datetime.fromisoformat(analysis["date"].replace("Z", "+00:00"))
                date_str = date_obj.strftime(self.scan_date_format)
            except:
                date_str = datetime.now().strftime(self.scan_date_format)
        else:
            date_str = datetime.now().strftime(self.scan_date_format)

        # Extract document type
        doc_type = analysis.get("document_type", "document")
        if doc_type == "other":
            doc_type = "file"

        # Generate summary (slugified)
        summary = analysis.get("summary", "document")
        summary = re.sub(r"[^\w\s-]", "", summary)[:50]  # Limit length
        summary = re.sub(r"[-\s]+", "_", summary).strip("_").lower()

        # Extract entities for additional context
        entities = analysis.get("entities", [])
        if entities:
            entity_str = entities[0].replace(" ", "_").lower()[:20]
            summary = f"{summary}_{entity_str}" if len(summary) < 30 else summary

        # Replace pattern placeholders
        filename = self.filename_pattern
        filename = filename.replace("{date}", date_str)
        filename = filename.replace("{type}", doc_type)
        filename = filename.replace("{summary}", summary)

        # Ensure .pdf extension
        if not filename.lower().endswith(".pdf"):
            filename += ".pdf"

        # Clean up filename
        filename = re.sub(r"[^\w\s.-]", "", filename)
        filename = re.sub(r"[-\s]+", "_", filename)

        return filename

    def process_pdf(self, file_path: str, original_filename: str) -> bool:
        """Process a single PDF file."""
        logger.info(f"Processing file: {original_filename}")

        try:
            # Download file to local temp directory
            local_path = os.path.join(self.data_dir, original_filename)
            self.webdav_client.download_sync(remote_path=file_path, local_path=local_path)

            # Extract text from PDF
            text = self.extract_text_from_pdf(local_path)

            if not text:
                logger.warning(f"No text extracted from {original_filename}, skipping")
                return False

            # Analyze with AI
            analysis = self.analyze_document_with_ai(text)

            if not analysis:
                logger.warning(f"AI analysis failed for {original_filename}")
                return False

            # Check confidence
            if analysis.get("confidence", 0) < self.min_confidence:
                logger.warning(f"Low confidence ({analysis.get('confidence')}) for {original_filename}")

            # Generate new filename
            new_filename = self.generate_filename(analysis, original_filename)

            logger.info(f"Original: {original_filename} -> New: {new_filename}")

            # Upload to output folder
            output_path = os.path.join(self.output_folder, new_filename)
            self.webdav_client.upload_sync(
                remote_path=output_path,
                local_path=local_path,
            )

            # Optionally delete from source folder
            # self.webdav_client.delete(file_path)

            # Remove local file
            if os.path.exists(local_path):
                os.remove(local_path)

            logger.success(f"Successfully processed {original_filename}")
            return True

        except Exception as e:
            logger.error(f"Error processing {original_filename}: {e}")
            return False

    def check_for_new_files(self):
        """Check WebDAV folder for new files to process."""
        if not self.webdav_client:
            logger.error("WebDAV client not initialized")
            return

        try:
            # List files in watch folder
            files = self.webdav_client.list(self.watch_folder)

            for filename in files:
                if isinstance(filename, str) and filename.endswith(".pdf"):
                    file_path = os.path.join(self.watch_folder, filename)

                    # Check if already processed (using file hash)
                    file_hash = self._get_file_hash(file_path)

                    if file_hash and file_hash not in self.processed_files:
                        self.processed_files[file_hash] = filename
                        self.process_pdf(file_path, filename)
                    elif file_hash:
                        logger.debug(f"File already processed: {filename}")

        except WebDavException as e:
            logger.error(f"WebDAV error checking for files: {e}")
        except Exception as e:
            logger.error(f"Error checking for new files: {e}")

    def _get_file_hash(self, file_path: str) -> Optional[str]:
        """Get MD5 hash of a file."""
        try:
            # Download file to calculate hash
            local_path = os.path.join(self.data_dir, "temp_hash.pdf")
            self.webdav_client.download_sync(remote_path=file_path, local_path=local_path)

            with open(local_path, "rb") as f:
                file_hash = hashlib.md5(f.read()).hexdigest()

            os.remove(local_path)
            return file_hash

        except Exception as e:
            logger.error(f"Error calculating file hash: {e}")
            return None

    def run(self, web_mode=False):
        """Main loop to continuously monitor for new files.

        Args:
            web_mode: If True, only run once and return (for web interface control).
                     If False, run continuously with check_interval.
                     If check_interval is 0, monitoring is disabled.
        """
        if web_mode:
            logger.info("Running in web mode - single check")
            self.check_for_new_files()
            return

        if self.check_interval == 0:
            logger.info("Check interval is 0 - automatic monitoring disabled")
            logger.info("Use the web interface to manually trigger processing")
            # Keep the process alive but don't process automatically
            while True:
                time.sleep(3600)  # Sleep for an hour, just to keep process alive

        logger.info(f"Starting PDF processor, checking every {self.check_interval} seconds")

        while True:
            self.check_for_new_files()
            time.sleep(self.check_interval)


def main():
    """Main entry point."""
    import sys

    # Check if web mode is requested
    if "--web" in sys.argv:
        # Run with web interface
        from src.webapp import WebApp

        processor = PDFProcessor()

        # If check_interval is 0, run in web mode only
        if processor.check_interval == 0:
            logger.info("Check interval is 0 - running in web-only mode")

        webapp = WebApp(processor)
        logger.info(
            f"Starting web interface on http://{processor.settings.web_host}:"
            f"{processor.settings.web_port}"
        )
        webapp.run(
            host=processor.settings.web_host,
            port=processor.settings.web_port,
        )
    else:
        # Run in CLI mode
        processor = PDFProcessor()
        processor.run()


if __name__ == "__main__":
    main()
