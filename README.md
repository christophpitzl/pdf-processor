# PDF Processor

[![GHCR](https://github.com/christophpitzl/pdf-processor/actions/workflows/docker-publish.yml/badge.svg)](https://github.com/christophpitzl/pdf-processor/actions/workflows/docker-publish.yml)

> A Docker-based tool that monitors an NFS-mounted folder for newly uploaded PDF documents, analyzes their content using a local LLM via Ollama, and renames them based on the analyzed content.

**Recommended Model**: `granite4.1:3b` - provides clean JSON responses without markdown wrapping.

## Overview

This project solves the problem of disorganized PDF files that are uploaded from mobile scanning apps. Instead of keeping filenames based on scan timestamps, this processor:

1. Monitors an NFS-mounted directory for new PDF files
2. Extracts text content from PDFs (including OCR)
3. Analyzes the content using a **local** AI model via Ollama (no cloud API calls)
4. Generates meaningful filenames based on document type, date, and summary
5. Moves processed files to an output folder with the new name

All processing happens entirely on your local infrastructure — no sensitive document data is ever sent to an external cloud provider.

## Features

- **NFS Integration**: Watches directories on an NFS share — works with any NAS that exports NFS
- **Local AI Analysis**: Uses Ollama with local models — no data leaves your network
- **Privacy-First**: All document content stays on-premises; no cloud API keys needed
- **Smart Filename Generation**: Creates descriptive filenames like `2024-05-14_invoice_acme_corp.pdf`
- **Configurable**: Easy to customize through environment variables
- **Continuous Monitoring**: Runs as a daemon, checking for new files at regular intervals
- **Web Dashboard**: Modern web UI for monitoring and manual processing triggers

## Prerequisites

- Docker and Docker Compose installed
- An NFS export from your NAS (Synology, QNAP, TrueNAS, etc.)
- The NFS share mounted on the Docker host
- [Ollama](https://ollama.com/) installed and running separately on your host or another machine
- A local LLM model pulled in Ollama (e.g., `granite4.1:3b`, `qwen3.5:0.8b`, `mistral`, `gemma2`)
  - **Note**: `granite4.1:3b` is recommended as it returns clean JSON without markdown code blocks

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

### Step 2: Mount the NFS Share on the Docker Host

Ensure the NFS export from your NAS is mounted locally. Add an entry to `/etc/fstab`:

```bash
# /etc/fstab — replace <nfs-server> and <export-path> with your values
<nfs-server>:/volume1/scans  /mnt/nfs  nfs  hard,intr,noatime  0  0
```

Then mount it:

```bash
sudo mkdir -p /mnt/nfs
sudo mount /mnt/nfs
```

Create the `incoming` and `processed` subdirectories:

```bash
sudo mkdir -p /mnt/nfs/incoming /mnt/nfs/processed
```

Configure your scanning app (e.g., Adobe Scan, CamScanner) to upload PDFs into the `incoming` folder on the NFS share.

### Step 3: Configure Environment

Copy the example environment file and configure your settings:

```bash
cp .env.example .env
```

Edit `.env` and set at minimum:

- `OLLAMA_BASE_URL` — URL of your Ollama server (e.g., `http://ollama.pitzl.net:11434`)
- `NFS_WATCH_DIR` — Path to the incoming directory (default: `/mnt/nfs/incoming`)
- `NFS_OUTPUT_DIR` — Path to the processed directory (default: `/mnt/nfs/processed`)

All other variables have built-in defaults.

### Step 4: Start the Container

```bash
docker compose up -d
```

This will pull the `latest` image from `ghcr.io/christophpitzl/pdf-processor`.

The web interface is available at `http://localhost:8080`.

## Usage

### NFS Folder Layout

```
/mnt/nfs/              # NFS mount root (bind-mounted into container)
├── incoming/          # Drop PDFs here (from scanner apps)
└── processed/         # Renamed PDFs appear here
```

### Web Interface

The dashboard provides:
- **Input count** — PDFs waiting in the incoming folder
- **Processing status** — Idle or running
- **Output count** — Successfully processed PDFs
- **Start Processing** button — manually trigger batch processing
- **Run Diagnostics** button — comprehensive system health check (NFS mount, Ollama, folders)
- **Configuration display** — shows current settings

### Architecture Change: WebDAV → NFS

This version replaces the previous WebDAV-based file access with direct NFS filesystem operations. Benefits:

- **No HTTP overhead** — files are read/written directly via the local filesystem
- **No credentials** — NFS handles authentication at the mount level
- **Simpler code** — uses standard Python `pathlib` and `shutil` instead of a remote client library
- **Better performance** — file operations are as fast as the network and NFS protocol allow
- **Fewer failure modes** — eliminates HTTP errors, SSL issues, and WebDAV-specific quirks

## Configuration

All configuration parameters have **sensible built-in defaults** defined in `src/config.py`. You only need to override values you want to customize.

### Full Reference — Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `NFS_WATCH_DIR` | `/mnt/nfs/incoming` | NFS directory to monitor for new PDFs |
| `NFS_OUTPUT_DIR` | `/mnt/nfs/processed` | NFS directory for renamed PDFs |
| `NFS_SERVER` | — | NFS server address (diagnostics only) |
| `NFS_EXPORT_PATH` | — | NFS export path (diagnostics only) |
| `NFS_MOUNT_OPTIONS` | `hard,intr,noatime` | NFS mount options (diagnostics only) |
| `NFS_HOST_MOUNT` | `/mnt/nfs` | Host path to bind-mount into the container |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API base URL |
| `OLLAMA_MODEL` | `granite4.1:3b` | Local model to use for analysis |
| `OLLAMA_WOL_ENABLED` | `false` | Enable Wake-on-LAN to wake up Ollama server |
| `OLLAMA_MAC_ADDRESS` | — | MAC address of Ollama server's NIC |
| `OLLAMA_BROADCAST_HOST` | `255.255.255.255` | Broadcast IP for WOL magic packet |
| `OLLAMA_WOL_PORT` | `9` | UDP port for WOL magic packet |
| `OLLAMA_WOL_RETRIES` | `10` | Max retries waiting for Ollama to become available |
| `OLLAMA_WOL_RETRY_DELAY` | `5.0` | Seconds between WOL retry attempts |
| `SCAN_DATE_FORMAT` | `%Y-%m-%d` | Date format for generated filenames |
| `MIN_CONFIDENCE` | `0.6` | Minimum confidence score for processing |
| `FILENAME_PATTERN` | `{date}_{type}_{summary}.pdf` | Pattern for new filenames |
| `CHECK_INTERVAL` | `60` | Seconds between file checks (0 = disable auto-check) |
| `WEB_HOST` | `0.0.0.0` | Host to bind the web interface to |
| `WEB_PORT` | `8080` | Port for the web interface |
| `DATA_DIR` | `./data` | Local directory for temporary file storage |
| `LOGS_DIR` | `./logs` | Directory for log files |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |

> **Note:** All defaults are defined once in `src/config.py`. If you ever need to reset to factory defaults, simply remove the variable from your `.env` file.

### Filename Pattern Placeholders

- `{date}` — Document date or current date
- `{type}` — Document type (invoice, receipt, contract, etc.)
- `{summary}` — Brief summary of document content

## Web Interface

The PDF Processor includes a modern web interface for monitoring and controlling the processing.

### Features

- **Dashboard**: View real-time status of input folder, processing state, and output folder
- **Manual Processing**: Start processing with a button click — runs until input folder is empty
- **Configurable Check Interval**: Set `CHECK_INTERVAL` to control automatic monitoring
  - `CHECK_INTERVAL=0` — Disables automatic checking, web interface only
  - `CHECK_INTERVAL=60` — Check every 60 seconds (default)

### Accessing the Web Interface

When running with Docker Compose, the web interface is available at:

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
5. **Diagnostics Button** — Runs a comprehensive health check (NFS mount, Ollama, folders, config)
6. **Configuration Display** — Shows current check interval setting

## Docker Compose

The provided `docker-compose.yml` expects:

- NFS share mounted at `/mnt/nfs` on the Docker host
- Subdirectories `incoming/` and `processed/` inside the mount

The container bind-mounts the host's NFS mount point, making files directly accessible.

### Custom NFS Host Mount Path

If your NFS share is mounted at a different path on the host, set `NFS_HOST_MOUNT`:

```bash
# In .env:
NFS_HOST_MOUNT=/srv/nfs/scans
```

## Local AI Model Selection

The processor uses Ollama, which gives you full control over which model to run locally. Since all inference happens on your own hardware, choose a model that fits your available resources.

### Recommended Models

| Model | Parameters | RAM Required | Quality |
|-------|-----------|--------------|---------|
| **granite4.1:3b** (default) | 3B | ~6GB | Recommended: clean JSON without markdown |
| **mistral** | 7B | ~8GB | Excellent document understanding |
| **gemma2** | 9B | ~10GB | Great multilingual support |
| **llama3.1** | 8B | ~8GB | Strong general purpose |

### Pulling a Model

```bash
# Pull the default model
ollama pull granite4.1:3b

# Pull an alternative model
ollama pull mistral
```

> **💡 Tip:** Start with `granite4.1:3b` — it returns clean JSON without markdown wrapping.

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
│  Scanner App → NFS /incoming/   │
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
│  Copy → NFS /processed/         │
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
│   ├── utils/
│   │   └── wol.py          # Wake-on-LAN utilities
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

## Wake-on-LAN (WOL)

If your Ollama server is not always running, you can enable Wake-on-LAN to automatically wake it up before processing begins.

```bash
# Enable WOL (set to true)
OLLAMA_WOL_ENABLED=true

# MAC address of the Ollama server's network interface
OLLAMA_MAC_ADDRESS=AA:BB:CC:DD:EE:FF
```

When WOL is enabled, the processor will:

1. Send a magic packet to wake up the Ollama server
2. Wait for the Ollama API to become available (with retries)
3. Proceed with PDF processing once the server is ready

> **Note**: WOL requires that your Ollama server's network interface supports Wake-on-LAN and is configured to accept magic packets.

## Versioning

Docker images are tagged with:

| Tag | Description |
|---|---|
| `latest` | Stable production releases (updated on Git version tags) |
| `v1.0.0`, `v0.3` | Semantic version tags |
| `main` | Latest main branch build (may be unstable) |
| `sha-xxxxx` | Specific commit builds |

See the [packages page](https://github.com/christophpitzl/pdf-processor/pkgs/container/pdf-processor) for all available tags.
       │
       │ New PDF uploaded
       ▼
┌─────────────┐
│  Download   │
│   to temp   │
└──────┬──────┘
       │
       │ Extract text
       ▼
┌─────────────┐
│   PDF       │
│  Analysis   │
└──────┬──────┘
       │
       │ AI Analysis
       ▼
┌─────────────┐
│  Generate   │
│  filename   │
└──────┬──────┘
       │
       │ Move processed file to
       ▼
┌──────────────────────┐
│  NFS /processed/     │
└──────────────────────┘
```

## Troubleshooting

### Common Issues

**1. NFS Mount Not Available**
- Verify the NFS share is mounted: `mount | grep nfs`
- Check `/etc/fstab` for the correct NFS entry
- Ensure the NFS server is reachable: `showmount -e <nfs-server>`
- Check container logs: `docker compose logs pdf-processor`

**2. AI Analysis Fails**
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
# Include entity names
FILENAME_PATTERN={date}_{type}_{summary}_{entities}.pdf

# Use underscores instead of hyphens
FILENAME_PATTERN={date}_{type}_{summary}.pdf
```

### Adding Custom Document Types

Modify the prompt in `src/main.py` to recognize additional document types.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Acknowledgments

- Uses [Ollama](https://ollama.com/) for local AI model inference
- Built with Python, Docker, and NFS
- PDF processing powered by PyPDF2 and pdfplumber
