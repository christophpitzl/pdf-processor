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
- [Ollama](https://ollama.com/) — pulled automatically as a Docker service
- A local LLM model pulled in Ollama (e.g., `llama3.2`, `mistral`, `gemma2`)

## Usage

### Using Docker Compose (recommended)

Create a `.env` file (see [Configuration](#configuration)) and run:

```bash
docker compose up -d
```

This starts both the Ollama service and the PDF processor. On first run, you'll need to pull a model into Ollama:

```bash
# Pull the default model
docker compose exec ollama ollama pull llama3.2

# Or pick another model (mistral, gemma2, etc.)
docker compose exec ollama ollama pull mistral
```

### Using the GHCR image

```bash
docker run --rm -it \
  -e WEBDAV_URL=https://your-nas/webdav \
  -e WEBDAV_USERNAME=user \
  -e WEBDAV_PASSWORD=pass \
  -e OLLAMA_BASE_URL=http://host.docker.internal:11434 \
  ghcr.io/christophpitzl/pdf-processor:latest
```

### Building locally

```bash
docker build -t pdf-processor .
docker run --rm -it --env-file .env pdf-processor
```

### View Logs

```bash
docker compose logs -f
```

### Stop the Container

```bash
docker compose down
```

## Configuration

### Environment Variables

Create a `.env` file in the project directory:

```bash
# WebDAV Configuration
WEBDAV_URL=http://nas.local/webdav
WEBDAV_USERNAME=your_username
WEBDAV_PASSWORD=your_password

# Folder paths (relative to WebDAV root)
WEBDAV_WATCH_FOLDER=/incoming
WEBDAV_OUTPUT_FOLDER=/processed

# Ollama Configuration
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_MODEL=llama3.2

# Processing Configuration
SCAN_DATE_FORMAT=%Y-%m-%d
MIN_CONFIDENCE=0.6
FILENAME_PATTERN={date}_{type}_{summary}.pdf
CHECK_INTERVAL=60

# Logging
LOG_LEVEL=INFO
```

### Configuration Options

| Variable | Default | Description |
|----------|---------|-------------|
| `WEBDAV_URL` | http://nas.local/webdav | URL of your WebDAV server |
| `WEBDAV_USERNAME` | - | WebDAV username |
| `WEBDAV_PASSWORD` | - | WebDAV password |
| `WEBDAV_WATCH_FOLDER` | /incoming | Folder to monitor for new PDFs |
| `WEBDAV_OUTPUT_FOLDER` | /processed | Folder to save processed files |
| `OLLAMA_BASE_URL` | http://localhost:11434 | Ollama API base URL |
| `OLLAMA_MODEL` | llama3.2 | Local model to use for analysis |
| `SCAN_DATE_FORMAT` | %Y-%m-%d | Date format for generated filenames |
| `MIN_CONFIDENCE` | 0.6 | Minimum confidence score for processing |
| `FILENAME_PATTERN` | {date}_{type}_{summary}.pdf | Pattern for new filenames |
| `CHECK_INTERVAL` | 60 | Seconds between file checks |
| `LOG_LEVEL` | INFO | Logging level (DEBUG, INFO, WARNING, ERROR) |

### Filename Pattern Placeholders

- `{date}` - Document date or current date
- `{type}` - Document type (invoice, receipt, contract, etc.)
- `{summary}` - Brief summary of document content


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
├── tests/                  # Test suite
├── data/                   # Sample PDFs (tracked with Git LFS)
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
