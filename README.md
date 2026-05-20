# PDF Processor

[![GHCR](https://github.com/christophpitzl/pdf-processor/actions/workflows/docker-publish.yml/badge.svg)](https://github.com/christophpitzl/pdf-processor/actions/workflows/docker-publish.yml)

> A Docker-based tool that monitors a host-mounted folder for newly uploaded PDF documents, analyzes their content using a local LLM via Ollama, and renames them based on the analyzed content.

**Recommended Model**: `gemma4:e2b` - provides clean JSON responses without markdown wrapping.

## Overview

This project solves the problem of disorganized PDF files that are uploaded from mobile scanning apps. Instead of keeping filenames based on scan timestamps, this processor:

1. Monitors `/incoming` (host-mounted folder) for new PDF files
2. Extracts text content from PDFs (including OCR)
3. Analyzes the content using a **local** AI model via Ollama (no cloud API calls)
4. Generates meaningful filenames based on document type, date, and summary
5. Moves processed files to `/processed` with the new name

All processing happens entirely on your local infrastructure — no sensitive document data is ever sent to an external cloud provider.

## Features

- **Host-Mounted Folders**: Map any host directories to `/incoming` and `/processed` via Docker volumes — works with local folders, NFS mounts on the host, or any filesystem your host can access
- **Local AI Analysis**: Uses Ollama with local models — no data leaves your network
- **Privacy-First**: All document content stays on-premises; no cloud API keys needed
- **Smart Filename Generation**: Creates descriptive filenames like `2024-05-14_invoice_acme_corp.pdf`
- **Configurable**: Easy to customize through environment variables
- **Language Selection**: Choose between German (default) or English for AI-generated summaries in filenames
- **Continuous Monitoring**: Runs as a daemon, checking for new files at regular intervals
- **Web Dashboard**: Modern web UI for monitoring, manual processing triggers, stop button, and progress bar
- **No Privileged Mode**: The container no longer needs `privileged: true` or `SYS_ADMIN` capabilities

## Prerequisites

- Docker and Docker Compose installed
- [Ollama](https://ollama.com/) installed and running separately on your host or another machine
- A local LLM model pulled in Ollama (e.g., `gemma4:e2b`, `qwen3.5:0.8b`, `mistral`, `gemma2`)
  - **Note**: `gemma4:e2b` is recommended as it returns clean JSON without markdown code blocks

**No NFS mounting inside the container!** Folders are mapped from the host via Docker volumes.
Simply point the container at any host directory — your PDFs can be on a local disk, an NFS share
mounted on the host, or any other filesystem your host can reach.

## Quick Start

### Step 1: Install and Run Ollama

First, install Ollama on your host machine or another server:

```bash
# On Linux/macOS
curl -fsSL https://ollama.com/install.sh | sh

# Start Ollama (runs as a service)
ollama serve
```

Then pull your desired model:

```bash
# Pull the recommended model (returns clean JSON)
ollama pull granite4.1:3b

# Or pick another model (mistral, gemma2, etc.)
ollama pull mistral
```

Ollama will be available at `http://<your-ollama-server>:11434`. Note the IP address or hostname.

### Step 2: Create Host Folders

Create the folders on your host that will hold the PDFs:

```bash
mkdir -p /path/to/pdf-incoming /path/to/pdf-processed
```

Configure your scanning app (e.g., Adobe Scan, CamScanner) to upload PDFs to `/path/to/pdf-incoming`.

### Step 3: Configure Environment

Copy the example environment file and configure your settings:

```bash
cp .env.example .env
```

Edit `.env` and set at minimum:

- `OLLAMA_BASE_URL` — URL of your Ollama server (e.g., `http://<your-ollama-server>:11434`)

All other variables have built-in defaults.

### Step 4: Start the Container

```bash
docker compose up -d
```

This will pull the `latest` image from `ghcr.io/christophpitzl/pdf-processor`.

The web interface is available at `http://localhost:8080`.

### Folder Layout

The container uses host-mounted volumes — no NFS mounting inside the container:

```
Host machine:
  /path/to/pdf-incoming/        # Drop PDFs here (mapped to /incoming in container)
  /path/to/pdf-processed/       # Renamed PDFs appear here (mapped to /processed)

Container:
  /incoming/                    # Watch directory (mapped from host)
  /processed/                   # Output directory (mapped from host)
  /app/data/                    # Internal temp storage (not user-facing)
  /app/logs/                    # Application logs (not user-facing)
```

Configure the host paths in `docker-compose.yml` under `volumes`:

```yaml
volumes:
  - /path/to/pdf-incoming:/incoming
  - /path/to/pdf-processed:/processed
```

> **💡 Tip:** If your scanning app uploads to `/mnt/nas/upload` and you want processed
> files in `/mnt/nas/done`, just update the volume mappings in `docker-compose.yml`:
> ```yaml
> volumes:
>   - /mnt/nas/upload:/incoming
>   - /mnt/nas/done:/processed
> ```

## Usage

### Web Interface

The dashboard provides:
- **Input count** — PDFs waiting in the incoming folder
- **Processing status** — Idle or running with real-time progress bar
- **Output count** — Successfully processed PDFs
- **Start Processing** button — manually trigger batch processing
- **Stop button** — gracefully stop processing after the current file
- **Language selector** — switch between German and English for AI-generated summaries
- **Configuration display** — shows current settings and language

### Architecture Change: Internal NFS → Host-Mounted Volumes

This version replaces the previous internal NFS auto-mounting with host-managed volume mounts. Benefits:

- **No privileged mode required** — the container no longer needs `privileged: true` or `SYS_ADMIN`
- **Simpler networking** — no need for the container to reach NFS servers directly
- **More flexible storage** — the host can mount anything (NFS, SMB, local disk, etc.)
- **Better security** — container runs with reduced privileges
- **Standard Docker pattern** — uses standard Docker volume mounts familiar to all Docker users

## Configuration

All configuration parameters have **sensible built-in defaults** defined in `src/config.py`. You only need to override values you want to customize.

### Full Reference — Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API base URL |
| `OLLAMA_MODEL` | `gemma4:e2b` | Local model to use for analysis |
| `SCAN_DATE_FORMAT` | `%Y-%m-%d` | Date format for generated filenames |
| `MIN_CONFIDENCE` | `0.6` | Minimum confidence score for processing |
| `FILENAME_PATTERN` | `{date}_{type}_{summary}.pdf` | Pattern for new filenames |
| `CHECK_INTERVAL` | `60` | Seconds between file checks (0 = disable auto-check) |
| `LANGUAGE` | `de` | Language for AI-generated summaries (`de` for German, `en` for English) |
| `WEB_HOST` | `0.0.0.0` | Host to bind the web interface to |
| `WEB_PORT` | `8080` | Port for the web interface |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |

> **Note:** All defaults are defined once in `src/config.py`. If you ever need to reset to factory defaults, simply remove the variable from your `.env` file.

### Filename Pattern Placeholders

- `{date}` — Document date or current date
- `{type}` — Document type (invoice, receipt, contract, etc.)
- `{summary}` — Brief summary of document content
- `{entities}` — Important entities (company names, person names, etc.) — only included if specified in pattern

## Web Interface

The PDF Processor includes a modern web interface for monitoring and controlling the processing.

### Features

- **Dashboard**: View real-time status of input folder, processing state, and output folder
- **Manual Processing**: Start processing with a button click — runs until input folder is empty
- **Configurable Check Interval**: Set `CHECK_INTERVAL` to control automatic monitoring
  - `CHECK_INTERVAL=0` — Disables automatic checking, web interface only
  - `CHECK_INTERVAL=60` — Check every 60 seconds (default)

```
http://localhost:8080
```

Or configure the host and port using environment variables:

```bash
WEB_HOST=0.0.0.0 WEB_PORT=9090 docker compose up -d
```

### Web Interface Dashboard

The dashboard shows:

1. **Input Folder Count** — Number of PDF documents waiting to be processed
2. **Processing Status** — Current state (Idle/Running)
3. **Output Folder Count** — Number of successfully processed PDF documents
4. **Manual Trigger Button** — Starts processing all documents in the input folder until empty
5. **Diagnostics Button** — Runs a comprehensive health check (folders, Ollama, config)
6. **Configuration Display** — Shows current check interval setting

## Docker Compose

The provided `docker-compose.yml` will:

- Map host folders to `/incoming` and `/processed` inside the container
- Create the folders if they don't exist on the host
- Run without privileged mode (no `SYS_ADMIN` capabilities needed)

Configure the host folder paths in `docker-compose.yml` under the `volumes` section to point at your directories.

## Local AI Model Selection

The processor uses Ollama, which gives you full control over which model to run locally. Since all inference happens on your own hardware, choose a model that fits your available resources.

### Recommended Models

| Model | Parameters | RAM Required | Quality |
|-------|-----------|--------------|---------|
| **gemma4:e2b** (default) | 3B | ~6GB | Recommended: clean JSON without markdown |
| **mistral** | 7B | ~8GB | Excellent document understanding |
| **gemma2** | 9B | ~10GB | Great multilingual support |
| **llama3.1** | 8B | ~8GB | Strong general purpose |

### Pulling a Model

```bash
# Pull the default model
ollama pull gemma4:e2b

# Pull an alternative model
ollama pull mistral
```

> **💡 Tip:** Start with `gemma4:e2b` — it returns clean JSON without markdown wrapping.

## Document Types

The AI can recognize and categorize various document types:

- Invoice
- Receipt
- Contract
- Letter
- Report
- Other

## File Processing Flow

```
┌─────────────────────────────────┐
│  Scanner App → /incoming/       │
│  (host-mounted folder)          │
└────────────┬────────────────────┘
             │
             ▼
┌─────────────────────────────────┐
│  PDF Processor detects new file │
│  (polling interval)             │
└────────────┬────────────────────┘
             │
             ▼
┌─────────────────────────────────┐
│  Extract text (pdfplumber +     │
│  PyPDF2 fallback)               │
└────────────┬────────────────────┘
             │
             ▼
┌─────────────────────────────────┐
│  Analyze with Ollama LLM        │
│  → document type, date, summary │
└────────────┬────────────────────┘
             │
             ▼
┌─────────────────────────────────┐
│  Generate new filename          │
│  → 2024-05-14_invoice_acme.pdf │
└────────────┬────────────────────┘
             │
             ▼
┌─────────────────────────────────┐
│  Copy → /processed/             │
│  Delete original from /incoming/│
└─────────────────────────────────┘
```

## Development

### Project Structure

```
.
├── .devcontainer/          # Dev container config
│   ├── Dockerfile
│   └── devcontainer.json
├── .github/workflows/      # CI/CD
│   └── docker-publish.yml  # Builds & pushes image to GHCR
├── src/                    # Application source
│   ├── config.py           # Centralized settings with defaults
│   ├── main.py             # PDF processor core
│   ├── webapp.py           # Flask web interface
│   └── templates/
│       └── index.html      # Web dashboard
├── tests/                  # Test suite
├── data/                   # Sample PDFs (tracked with Git LFS)
├── .env.example            # Reference for all configurable variables
├── .gitignore
├── AGENTS.md               # Copilot agent instructions
└── README.md
```

### Commands

```bash
pip install -e ".[dev]"    # Install with dev dependencies
ruff check src/ tests/      # Lint
black src/ tests/           # Format
mypy src/                   # Type check
pytest --cov=src/           # Test with coverage
python -m src.main --web    # Run with web interface
```

## Versioning

Docker images are tagged with:

| Tag | Description |
|---|---|
| `latest` | Stable production releases (updated on Git version tags) |
| `v1.0.0`, `v0.3` | Semantic version tags |

See the [packages page](https://github.com/christophpitzl/pdf-processor/pkgs/container/pdf-processor) for all available tags.

## Troubleshooting

### Common Issues

**1. Folders Not Accessible**
- Verify the host directories exist and are readable/writable
- Check Docker volume mappings in `docker-compose.yml` are correct
- Check container logs: `docker compose logs pdf-processor`
- The container will create the folders if they don't exist (if permissions allow)

**2. AI Analysis Fails**
- Verify Ollama is running: `curl http://<ollama-host>:11434/api/tags`
- Check which model is pulled: `ollama list`
- Ensure the model name in `OLLAMA_MODEL` matches a pulled model
- If using a remote Ollama host, verify `OLLAMA_BASE_URL` is reachable
- Verify Ollama is running: `curl http://<ollama-host>:11434/api/tags`
- Check which model is pulled: `ollama list`
- Ensure the model name in `OLLAMA_MODEL` matches a pulled model
- If using a remote Ollama host, verify `OLLAMA_BASE_URL` is reachable

**3. Low Confidence Scores**
- Increase `MIN_CONFIDENCE` threshold
- Ensure PDF text extraction is working properly
- Try a more powerful AI model

**4. Text Extraction Fails**
- Verify PDF files are not password protected
- Check if PDF contains actual text (not just images)
- Tesseract OCR is included for image-based PDFs

### Debug Mode

Set `LOG_LEVEL=DEBUG` in your `.env` file for more detailed logging.

## Customization

### Custom Filename Patterns

You can customize the filename pattern in `.env`:

```bash
# Include entity names (entities will only be added if {entities} is in the pattern)
FILENAME_PATTERN={date}_{type}_{summary}_{entities}.pdf

# Simple pattern without entities
FILENAME_PATTERN={date}_{type}_{summary}.pdf
```

### Adding Custom Document Types

Modify the prompt in `src/main.py` to recognize additional document types.

## Future Improvements (Memo)

The following aspects could be improved in future versions:

### 1. Smarter Date Handling
- **Current behavior**: When no date is recognized in the document, the current date is used as a fallback
- **Proposed improvement**: Only assign a date in the filename if the AI model detects a date with high confidence (e.g., confidence ≥ 0.8)
- **Benefit**: Avoids misleading filenames when no actual document date is found

### 2. Improved Summary Generation
- **Current behavior**: Summary and entity are treated as separate fields, often resulting in cutoff entities when appended to the filename
- **Proposed improvement**: Remove the separation between content summary and entity — let the AI model generate a single, cohesive short description that best represents the document
- **Implementation**: Modify the prompt to request one unified "description" field (max 30-40 characters) instead of separate "summary" and "entities" fields
- **Benefit**: More natural, readable filenames without artificial truncation or awkward concatenation

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Acknowledgments

- Uses [Ollama](https://ollama.com/) for local AI model inference
- Built with Python and Docker
- PDF processing powered by PyPDF2 and pdfplumber
