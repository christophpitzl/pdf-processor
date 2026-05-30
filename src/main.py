"""
PDF Processor - Main Application
Monitors a host-mounted folder for new PDF files, processes them with
local AI (Ollama), and renames them based on content.

Folders are mapped from the Docker host:
  - /incoming  → drop PDFs here
  - /processed → renamed PDFs appear here
"""

import os
import re
import time
import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

from loguru import logger
from dotenv import load_dotenv

# PDF processing
from PyPDF2 import PdfReader
import pdfplumber

# HTTP client for Ollama API
import httpx

# Centralized configuration
from src.config import Settings

# Load environment variables
load_dotenv()


class PDFProcessor:
    """Main class for processing PDF files from a host-mounted directory."""

    def __init__(self, settings: Optional[Settings] = None):
        """Initialize the PDF processor with configuration.

        Args:
            settings: A ``Settings`` instance.  When ``None`` the settings
                      are loaded from environment variables automatically.
        """
        self.settings = settings if settings is not None else Settings.from_env()
        s = self.settings  # short alias for convenience

        self.watch_dir = Path(s.incoming_dir)
        self.output_dir = Path(s.processed_dir)
        self.ollama_base_url = s.ollama_base_url
        self.ollama_model = s.ollama_model
        self.scan_date_format = s.scan_date_format
        self.min_confidence = s.min_confidence
        self.check_interval = s.check_interval
        self.log_level = s.log_level
        self.data_dir = s.data_dir
        self.logs_dir = s.logs_dir
        self.language = s.language

        # Stop flag for interrupting processing
        self._stop_requested = False
        # Progress tracking
        self.progress_total = 0
        self.progress_current = 0
        self.progress_errors = 0

        # Setup logging
        logger.remove()
        logger.add(
            Path(self.logs_dir) / "pdf-processor.log",
            level=self.log_level,
            rotation="10 MB",
            retention="30 days",
        )
        logger.add(lambda msg: print(msg, end=""), level=self.log_level)

        # Initialize Ollama HTTP client
        self.ollama_client = httpx.Client(
            base_url=self.ollama_base_url,
            timeout=httpx.Timeout(120.0, connect=10.0),
        )

        # Track processed files to avoid duplicates (keyed by absolute path)
        self.processed_files: Dict[str, str] = {}

        # Validate directories
        self._validate_required_directories()

        if not self.check_ollama_connection():
            logger.warning(
                "Ollama connection check failed. "
                "Document analysis will fail if Ollama is not running."
            )

    def _validate_required_directories(self) -> None:
        """Validate and create required directories if needed."""
        for label, path in [
            ("Data", Path(self.data_dir)),
            ("Logs", Path(self.logs_dir)),
            ("Incoming", self.watch_dir),
            ("Processed", self.output_dir),
        ]:
            try:
                if not path.exists():
                    logger.warning(f"{label} directory does not exist: {path}")
                    path.mkdir(parents=True, exist_ok=True)
                    logger.info(f"Created {label.lower()} directory: {path}")
                elif not path.is_dir():
                    logger.error(f"{label} path exists but is not a directory: {path}")
                elif not os.access(str(path), os.R_OK):
                    logger.error(f"{label} directory is not readable: {path}")
                else:
                    write_ok = (
                        os.access(str(path), os.W_OK) if label != "Logs" else True
                    )
                    if not write_ok:
                        logger.warning(f"{label} directory is not writable: {path}")
                    else:
                        logger.debug(f"{label} directory validated: {path}")
            except PermissionError:
                logger.error(
                    f"Permission denied accessing {label.lower()} directory: {path}"
                )
            except Exception as e:
                logger.error(f"Error validating {label.lower()} directory {path}: {e}")

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

    def check_ollama_connection(self) -> bool:
        """Check if Ollama server is reachable and model is available."""
        try:
            # Check if Ollama is running
            response = self.ollama_client.get("/api/tags", timeout=5.0)
            response.raise_for_status()
            models = response.json().get("models", [])

            # Check if our model is available
            model_names = [m.get("name", "") for m in models]
            if self.ollama_model not in model_names:
                logger.warning(
                    f"Model '{self.ollama_model}' not found in Ollama. Available models: {model_names}"
                )
                return False

            logger.info(
                f"Ollama connection successful, model '{self.ollama_model}' is available"
            )
            return True
        except httpx.RequestError as e:
            logger.error(f"Cannot connect to Ollama at {self.ollama_base_url}: {e}")
            return False
        except Exception as e:
            logger.error(f"Error checking Ollama connection: {e}")
            return False

    def analyze_document_with_ai(self, text: str) -> Dict[str, Any]:
        """Analyze document content using a local Ollama model."""
        if not text:
            logger.warning("No text to analyze")
            return {}

        # Determine language for description generation and document types
        if self.language == "de":
            language_instruction = "Generate the description in German language."
            document_types = "Rechnung|Quittung|Vertrag|Brief|Bericht|Sonstiges"
        else:
            language_instruction = "Generate the description in English language."
            document_types = "invoice|receipt|contract|letter|report|other"

        # Create prompt for document analysis
        description_max_chars = 35

        prompt = f"""Analyze the following document text and extract key information.

Return a JSON object with the following structure:
{{
    "document_type": "{document_types}",
    "date": "YYYY-MM-DD format if found, otherwise null",
    "description": "concise description, MAX {description_max_chars} characters, that naturally combines the document topic and key entities (company names, person names, etc.) into a single readable phrase",
    "confidence": "0.0-1.0 confidence score"
}}

{language_instruction}

Document text:
{text[:4000]}

IMPORTANT:
- Return ONLY the raw JSON object. Do NOT wrap it in markdown code blocks (no ```json or ```). Do NOT add any explanatory text. Only return valid JSON.
- The description must be a single cohesive phrase — do NOT return a separate list of entities. Incorporate entity names (company, person) directly into the description.
- Keep the description field under {description_max_chars} characters. This is critical for filename length limits."""

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

            response_data = response.json()
            logger.debug(f"Ollama full response: {response_data}")

            # Extract content from response
            if (
                "message" not in response_data
                or "content" not in response_data["message"]
            ):
                logger.error(f"Unexpected Ollama response structure: {response_data}")
                return {}

            content = response_data["message"]["content"].strip()
            logger.debug(
                f"Extracted content length: {len(content)}, content: {content[:200]}..."
            )

            if not content:
                logger.error("Ollama returned empty content")
                return {}

            # Clean up markdown code blocks if present
            # Models sometimes wrap JSON in ```json ... ``` blocks
            if content.startswith("```"):
                # Find the end of the code block
                lines = content.split("\n")
                cleaned_lines = []
                in_code_block = False
                for line in lines:
                    if line.strip().startswith("```"):
                        in_code_block = not in_code_block
                        continue
                    if in_code_block or not line.strip().startswith("```"):
                        cleaned_lines.append(line)
                content = "\n".join(cleaned_lines).strip()

            # Try to parse JSON from the response
            try:
                # Try to find JSON in the response
                json_start = content.find("{")
                json_end = content.rfind("}") + 1
                if json_start != -1 and json_end > json_start:
                    content = content[json_start:json_end]
                    logger.debug(f"Extracted JSON substring: {content[:200]}...")

                if not content:
                    logger.error("No JSON content found in Ollama response")
                    return {}

                result = json.loads(content)
                return result
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse Ollama response as JSON: {e}")
                logger.error(f"Response content that failed to parse: {content[:500]}")
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

    def generate_filename(
        self,
        analysis: Dict[str, Any],
        original_filename: str,
        file_path: Optional[Path] = None,
    ) -> str:
        """Generate new filename based on analysis and pattern."""
        if not analysis:
            return original_filename

        # Extract date from analysis, file metadata, or use current date
        date_str = ""
        date_source = "unknown"

        if analysis.get("date"):
            try:
                date_obj = datetime.fromisoformat(
                    analysis["date"].replace("Z", "+00:00")
                )
                date_str = date_obj.strftime(self.scan_date_format)
                date_source = "AI analysis"
            except ValueError:
                pass  # Will fall through to file metadata check

        # If no date from AI, try to get creation date from PDF metadata
        if not date_str and file_path and file_path.exists():
            try:
                import pdfplumber

                with pdfplumber.open(str(file_path)) as pdf:
                    if pdf.metadata and pdf.metadata.get("CreationDate"):
                        # PDF date format: D:YYYYMMDDHHmmSS...
                        creation_date = pdf.metadata["CreationDate"]
                        # Parse PDF date format
                        match = re.match(r"D:(\d{4})(\d{2})(\d{2})", creation_date)
                        if match:
                            year, month, day = match.groups()
                            date_obj = datetime(int(year), int(month), int(day))
                            date_str = date_obj.strftime(self.scan_date_format)
                            date_source = "PDF metadata"
            except Exception as e:
                logger.debug(f"Could not read PDF metadata from {file_path}: {e}")

        # Fallback to file system modification time or current date
        if not date_str:
            if file_path and file_path.exists():
                try:
                    stat = os.stat(str(file_path))
                    # Use file modification time (works on all platforms)
                    date_obj = datetime.fromtimestamp(stat.st_mtime)
                    date_str = date_obj.strftime(self.scan_date_format)
                    date_source = "file system"
                except Exception as e:
                    logger.debug(f"Could not get file time for {file_path}: {e}")

        # Final fallback to current date
        if not date_str:
            date_str = datetime.now().strftime(self.scan_date_format)
            date_source = "current date"

        logger.debug(
            f"Date source for {original_filename}: {date_source} -> {date_str}"
        )

        # Extract document type
        doc_type = analysis.get("document_type", "document")
        if doc_type == "other":
            doc_type = "file"

        def _slugify(value: str, max_len: int = 100) -> str:
            """Convert a string to a safe filename slug."""
            value = re.sub(r"[^\w\s-]", "", value)
            value = re.sub(r"[-\s]+", "_", value).strip("_").lower()
            if len(value) > max_len:
                value = value[:max_len].rstrip("_")
            return value

        # Unified description field
        description = _slugify(
            analysis.get("description") or analysis.get("summary", "document")
        )

        # Build filename
        filename = f"{date_str}_{doc_type}_{description}.pdf"

        # Clean up filename
        filename = re.sub(r"[^\w\s.-]", "", filename)
        filename = re.sub(r"[-\s]+", "_", filename)

        return filename

    def process_pdf(self, file_path: Path, original_filename: str) -> bool:
        """Process a single PDF file from the watch directory.

        Args:
            file_path: Absolute path to the PDF file.
            original_filename: The original filename (for logging).

        Returns:
            True if processing succeeded, False otherwise.
        """
        logger.info(f"Processing file: {original_filename}")

        # CRITICAL: Verify file still exists in incoming before processing
        if not file_path.exists():
            logger.error(f"File no longer exists in incoming folder: {file_path}")
            return False

        try:
            # Check for stop before starting
            if self._stop_requested:
                logger.info("Stop requested, aborting processing")
                return False

            # Copy file to local data dir for processing (handles network latency)
            local_path = Path(self.data_dir) / original_filename
            shutil.copy2(str(file_path), str(local_path))

            # Extract text from PDF
            text = self.extract_text_from_pdf(str(local_path))

            if not text:
                logger.warning(f"No text extracted from {original_filename}, skipping")
                self.progress_errors += 1
                # Clean up local copy
                if local_path.exists():
                    local_path.unlink()
                return False

            # Check for stop before AI analysis
            if self._stop_requested:
                logger.info("Stop requested before AI analysis")
                if local_path.exists():
                    local_path.unlink()
                return False

            # Analyze with AI
            analysis = self.analyze_document_with_ai(text)

            if not analysis:
                logger.warning(f"AI analysis failed for {original_filename}")
                logger.warning(f"File remains in incoming for retry: {file_path.name}")
                if local_path.exists():
                    local_path.unlink()
                return False

            # Check confidence
            if analysis.get("confidence", 0) < self.min_confidence:
                logger.warning(
                    f"Low confidence ({analysis.get('confidence')}) "
                    f"for {original_filename}"
                )

            # Generate new filename
            new_filename = self.generate_filename(
                analysis, original_filename, file_path
            )

            logger.info(f"Original: {original_filename} -> New: {new_filename}")

            # Move processed file to output directory with new name
            output_path = self.output_dir / new_filename

            # Handle duplicate filenames in output
            if output_path.exists():
                logger.warning(f"Output file already exists: {output_path}")
                # Add unique suffix to avoid overwriting
                base = output_path.stem
                suffix = output_path.suffix
                counter = 1
                while output_path.exists():
                    output_path = self.output_dir / f"{base}_{counter}{suffix}"
                    counter += 1
                logger.info(f"Using alternative filename: {output_path.name}")
                new_filename = output_path.name

            # Ensure output directory exists
            self.output_dir.mkdir(parents=True, exist_ok=True)

            # Step 1: Copy the processed file to output (with new name)
            shutil.copy2(str(local_path), str(output_path))
            logger.info(f"Copied file to output: {output_path}")

            # Step 2: CRITICAL - Verify the output file was created successfully
            if not output_path.exists():
                logger.error(f"CRITICAL: Output file was not created: {output_path}")
                logger.error(f"File REMAINS in incoming folder: {file_path}")
                if local_path.exists():
                    local_path.unlink()
                return False

            # Step 3: Only delete from incoming AFTER verifying output exists
            try:
                file_path.unlink(missing_ok=True)
                logger.info(f"Deleted original from incoming: {file_path.name}")
            except Exception as e:
                logger.error(f"Failed to delete original file {file_path}: {e}")
                logger.warning(
                    "File exists in BOTH incoming and processed folders - manual cleanup needed"
                )

            # Step 4: Verify original was deleted (optional check)
            if file_path.exists():
                logger.warning(
                    f"Original file still exists after deletion attempt: {file_path}"
                )

            # Remove local temp copy
            if local_path.exists():
                local_path.unlink()

            logger.success(f"Successfully processed {original_filename}")
            return True

        except Exception as e:
            logger.error(f"Error processing {original_filename}: {e}")
            logger.error(f"File remains in incoming folder for retry: {file_path}")
            return False

    def check_for_new_files(self) -> None:
        """Check the watch directory for new PDF files to process."""
        try:
            watch_path = self._resolve_watch_dir()

            if not watch_path.exists():
                logger.warning(
                    f"Watch directory does not exist: {watch_path}. "
                    "Make sure the directory is mapped as a Docker volume."
                )
                return

            # Gather PDF files (non-recursive, sorted by mtime for FIFO order)
            pdf_files: List[Path] = sorted(
                [
                    f
                    for f in watch_path.iterdir()
                    if f.is_file() and f.suffix.lower() == ".pdf"
                ],
                key=lambda p: p.stat().st_mtime,
            )

            if not pdf_files:
                logger.debug(f"No PDF files found in {watch_path}")
                return

            logger.info(f"Found {len(pdf_files)} PDF file(s) to process")

            # Reset progress for this batch
            self.progress_total = len(pdf_files)
            self.progress_current = 0
            self.progress_errors = 0
            self._stop_requested = False

            for file_path in pdf_files:
                # Check for stop before each file
                if self._stop_requested:
                    logger.info("Processing stopped by user request")
                    break

                # Compute hash to check for duplicates
                file_hash = self._get_file_hash(file_path)

                # Only skip if file was successfully processed before
                if file_hash and file_hash in self.processed_files:
                    logger.debug(
                        f"File already processed successfully: {file_path.name}"
                    )
                    # Remove from incoming since it's already processed
                    try:
                        file_path.unlink(missing_ok=True)
                        logger.info(
                            f"Removed duplicate from incoming: {file_path.name}"
                        )
                    except Exception as e:
                        logger.warning(
                            f"Could not remove duplicate {file_path.name}: {e}"
                        )
                    continue

                # Process the file
                logger.info(f"Starting processing of: {file_path.name}")
                success = self.process_pdf(file_path, file_path.name)
                if success:
                    # Only add to processed_files on success
                    if file_hash:
                        self.processed_files[file_hash] = file_path.name
                    logger.info(f"Completed processing: {file_path.name}")
                else:
                    logger.error(
                        f"Failed to process {file_path.name}. "
                        f"File remains in incoming folder for retry."
                    )
                self.progress_current += 1
                if not success:
                    self.progress_errors += 1

        except PermissionError:
            logger.error(
                f"Permission denied reading watch directory: " f"{self.watch_dir}"
            )
        except OSError as e:
            logger.error(f"I/O error checking for new files: {e}")
        except Exception as e:
            logger.error(f"Error checking for new files: {e}")

    def stop(self) -> None:
        """Request a graceful stop of processing."""
        self._stop_requested = True
        logger.info("Stop requested — processing will halt after current file")

    def _resolve_watch_dir(self) -> Path:
        """Resolve the watch directory, following symlinks if needed.

        Returns:
            The resolved Path.
        """
        try:
            return self.watch_dir.resolve()
        except Exception:
            return self.watch_dir

    def _get_file_hash(self, file_path: Path) -> Optional[str]:
        """Get MD5 hash of a local file.

        Args:
            file_path: Path to the file.

        Returns:
            MD5 hex digest string, or None on error.
        """
        try:
            return hashlib.md5(file_path.read_bytes()).hexdigest()
        except Exception as e:
            logger.error(f"Error calculating hash for {file_path}: {e}")
            return None

    def run(self, web_mode: bool = False) -> None:
        """Main loop to continuously monitor for new files.

        Args:
            web_mode: If True, only run once and return (for web interface
                      control).  If False, run continuously with
                      check_interval.  If check_interval is 0, monitoring
                      is disabled.
        """
        if web_mode:
            logger.info("Running in web mode — single check")
            self.check_for_new_files()
            return

        if self.check_interval == 0:
            logger.info("Check interval is 0 — automatic monitoring disabled")
            logger.info("Use the web interface to manually trigger processing")
            while True:
                time.sleep(3600)

        logger.info(f"Starting PDF processor, checking every {self.check_interval}s")

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
