# PDF Processor

[![GHCR](https://github.com/christophpitzl/pdf-processor/actions/workflows/docker-publish.yml/badge.svg)](https://github.com/christophpitzl/pdf-processor/actions/workflows/docker-publish.yml)

A Docker-based tool that monitors a WebDAV folder for newly uploaded PDF documents, analyzes their content using a **local** LLM via Ollama, and renames them based on the analyzed content.

## Overview

This project solves the problem of disorganized PDF files that are uploaded from mobile scanning apps. Instead of keeping filenames based on scan timestamps, this processor:

1. Monitors a WebDAV folder for new PDF files
2. Extracts text content from PDFs (including OCR)
3. Analyzes the content using a **local** AI model via Ollama (no cloud API calls)
4. Generates meaningful filenames based on document type, date, and summary
5. Saves processed files to an output folder

All processing happens entirely on your local infrastructure — no sensitive document data is ever sent to an external cloud provider.

## Features

- **WebDAV Integration**: Connects to your NAS WebDAV server
- **Local AI Analysis**: Uses Ollama with local models — no data leaves your network
- **Privacy-First**: All document content stays on-premises; no cloud API keys needed
- **Smart Filename Generation**: Creates descriptive filenames like `2024-05-14_invoice_acme_corp.pdf`
- **Configurable**: Easy to customize through environment variables
- **Continuous Monitoring**: Runs as a daemon, checking for new files at regular intervals

## Prerequisites

- Docker and Docker Compose installed
- Access to a WebDAV server (e.g., Nextcloud, Synology NAS, etc.)
- [Ollama](https://ollama.com/) installed and running separately on your host or another machine
- A local LLM model pulled in Ollama (e.g., `llama3.2`, `mistral`, `gemma2`)

## Usage

### Step 1: Install and Run Ollama Separately

First, install Ollama on your host machine or another server:

```bash
# On Linux/macOS
curl -fsSL https://ollama.com/install.sh | sh

# Start Ollama (runs as a service)
ollama serve
```

Then pull your desired model:

```bash
# Pull the default model
ollama pull llama3.2

# Or pick another model (mistral, gemma2, etc.)
ollama pull mistral
```

Ollama will be available at `http://<your-ollama-server>:11434`. Note the IP address or hostname of this server.

### Step 2: Run PDF Processor

#### Using Docker Compose (recommended)

Copy the reference env file and edit only what differs from the defaults:

```bash
cp .env.example .env
# Edit .env — at minimum set WEBDAV_USERNAME, WEBDAV_PASSWORD, and OLLAMA_BASE_URL
# All other variables will use their built-in defaults automatically.
```

Then run:

```bash
docker compose up -d
```

#### Using the GHCR image

```bash
docker run --rm -it \
  -e WEBDAV_URL=https://your-nas/webdav \
  -e WEBDAV_USERNAME=user \
  -e WEBDAV_PASSWORD=pass \
  -e OLLAMA_BASE_URL=http://<your-ollama-server>:11434 \
  ghcr.io/christophpitzl/pdf-processor:latest
```

#### Building locally

```bash
docker build -t pdf-processor .
docker run --rm -it --env-file .env pdf-processor
```

### Wake-on-LAN (WOL) — Wake Up Ollama Server Automatically

If your Ollama server is not always running, you can enable Wake-on-LAN to
automatically wake it up before processing begins. This is useful when the
server sleeps or is powered off.

```bash
# Enable WOL (set to true)
OLLAMA_WOL_ENABLED=true

# MAC address of the Ollama server's network interface
OLLAMA_MAC_ADDRESS=AA:BB:CC:DD:EE:FF
```

The remaining WOL parameters (`OLLAMA_BROADCAST_HOST`, `OLLAMA_WOL_PORT`,
`OLLAMA_WOL_RETRIES`, `OLLAMA_WOL_RETRY_DELAY`) already have sensible defaults
— you typically don't need to touch them.

When WOL is enabled, the processor will:
1. Send a magic packet to wake up the Ollama server
2. Wait for the Ollama API to become available (with retries)
3. Proceed with PDF processing once the server is ready

> **Note**: WOL requires that your Ollama server's network interface supports Wake-on-LAN and is configured to accept magic packets. The server must be on the same subnet or have a router that forwards WOL packets.

### View Logs

```bash
docker compose logs -f
```

### Stop the Container

```bash
docker compose down
```

## Configuration

All configuration parameters have **sensible built-in defaults** defined in
`src/config.py`. You only need to override the values you want to customize
— via a `.env` file or environment variables.

### Quick Start

Copy the reference file and edit only what you need:

```bash
cp .env.example .env
# Edit .env to set WEBDAV_USERNAME, WEBDAV_PASSWORD, OLLAMA_BASE_URL, etc.
docker compose up -d
```

Any variable not set in `.env` will automatically use its built-in default.

### Full Reference — Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `WEBDAV_URL` | `http://nas.local/webdav` | URL of your WebDAV server |
| `WEBDAV_USERNAME` | — | WebDAV username |
| `WEBDAV_PASSWORD` | — | WebDAV password |
| `WEBDAV_WATCH_FOLDER` | `/incoming` | Folder to monitor for new PDFs |
| `WEBDAV_OUTPUT_FOLDER` | `/processed` | Folder to save processed files |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API base URL |
| `OLLAMA_MODEL` | `llama3.2` | Local model to use for analysis |
| `OLLAMA_WOL_ENABLED` | `false` | Enable Wake-on-LAN to wake up Ollama server |
| `OLLAMA_MAC_ADDRESS` | — | MAC address of Ollama server's NIC |
| `OLLAMA_BROADCAST_HOST` | `[IP_ADDRESS]` | Broadcast IP for WOL magic packet |
| `OLLAMA_WOL_PORT` | `9` | UDP port for WOL magic packet |
| `OLLAMA_WOL_RETRIES` | `10` | Max retries waiting for Ollama to become available |
| `OLLAMA_WOL_RETRY_DELAY` | `5.0` | Seconds between WOL retry attempts |
| `SCAN_DATE_FORMAT` | `%Y-%m-%d` | Date format for generated filenames |
| `MIN_CONFIDENCE` | `0.6` | Minimum confidence score for processing |
| `FILENAME_PATTERN` | `{date}_{type}_{summary}.pdf` | Pattern for new filenames |
| `CHECK_INTERVAL` | `60` | Seconds between file checks (0 = disable auto-check) |
| `WEB_HOST` | `[IP_ADDRESS]` | Host to bind the web interface to |
| `WEB_PORT` | `8080` | Port for the web interface |
| `DATA_DIR` | `./data` | Local directory for temporary file storage |
| `LOGS_DIR` | `./logs` | Directory for log files |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |

> **Note:** All defaults are defined once in `src/config.py`. If you ever need
> to reset to factory defaults, simply remove the variable from your `.env`
> file.

### Filename Pattern Placeholders

- `{date}` - Document date or current date
- `{type}` - Document type (invoice, receipt, contract, etc.)
- `{summary}` - Brief summary of document content

## Web Interface

The PDF Processor includes a modern web interface for monitoring and controlling the processing.

### Features

- **Dashboard**: View real-time status of input folder, processing state, and output folder
- **Manual Processing**: Start processing with a button click - runs until input folder is empty
- **Configurable Check Interval**: Set `CHECK_INTERVAL` to control automatic monitoring
  - `CHECK_INTERVAL=0` - Disables automatic checking, web interface only
  - `CHECK_INTERVAL=60` - Check every 60 seconds (default)

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

1. **Input Folder Count** - Number of PDF documents waiting to be processed
2. **Processing Status** - Current state (Idle/Running)
3. **Output Folder Count** - Number of successfully processed PDF documents
4. **Manual Trigger Button** - Starts processing all documents in the input folder until empty
5. **Configuration Display** - Shows current check interval setting

### Running with Web Interface

The web interface is enabled by default in Docker. To run in CLI mode only (no web interface):

```bash
docker run --rm -it --env-file .env pdf-processor python -m src.main
```

To explicitly run with web interface:

```bash
docker run --rm -it --env-file .env -p 8080:8080 pdf-processor python -m src.main --web
```


## Development

This project includes a dev container configuration for VS Code / GitHub Codespaces.

### Dev Container

The dev container is based on `mcr.microsoft.com/devcontainers/base:ubuntu` with:

- Python 3, pip, venv
- Git LFS
- Common build tools

To open in a dev container:

1. Open the repository in VS Code
2. Run **Dev Containers: Reopen in Container**
3. Or open directly in [GitHub Codespaces](https://github.com/christophpitzl/pdf-processor)

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
python -m src.cli --help    # Run the CLI
```

## Versioning

Docker images are tagged with:

| Tag | Description |
|---|---|
| `latest` | Latest commit on `main` |
| `v0.1.0`, `0.1` | Semantic version tags |
| `<sha>` | Short commit hash |

See the [tags page](https://github.com/christophpitzl/pdf-processor/pkgs/container/pdf-processor) for all available tags.

## Local AI Model Selection

The processor uses Ollama, which gives you full control over which model to run locally. Since all inference happens on your own hardware, choose a model that fits your available resources.

### Recommended Models

| Model | Parameters | RAM Required | Quality |
|-------|-----------|--------------|---------|
| **llama3.2** (default) | 3B | ~4GB | Good for structured output |
| **mistral** | 7B | ~8GB | Excellent document understanding |
| **gemma2** | 9B | ~10GB | Great multilingual support |
| **llama3.1** | 8B | ~8GB | Strong general purpose |

### Pulling a Model

```bash
# Pull the default model
docker compose exec ollama ollama pull llama3.2

# Pull an alternative model
docker compose exec ollama ollama pull mistral
```

> **💡 Tip:** Start with `llama3.2` — it's small, fast, and works well for document classification tasks.
- **google/gemini-1.5-flash** - Fast multimodal processing
- **meta-llama/llama-3-70b-instruct** - Strong reasoning capabilities

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
┌─────────────┐
│  WebDAV     │
│  /incoming  │
└──────┬──────┘
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
       │ Upload to
       ▼
┌─────────────┐
│  WebDAV     │
│ /processed  │
└─────────────┘
```

## Troubleshooting

### Common Issues

**1. WebDAV Connection Failed**
- Verify WebDAV URL, username, and password
- Check if WebDAV service is running on your NAS
- Ensure network connectivity

**2. AI Analysis Fails**
- Verify Ollama is running: `docker compose ps`
- Check which model is pulled: `docker compose exec ollama ollama list`
- Ensure the model name in `OLLAMA_MODEL` matches a pulled model
- Check Ollama logs: `docker compose logs ollama`
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
- Built with Python, Docker, and WebDAV
- PDF processing powered by PyPDF2 and pdfplumber
