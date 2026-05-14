# PDF Processor

A Docker container that monitors a WebDAV folder for newly uploaded PDF documents, analyzes their content using AI, and renames them based on the analyzed content.

## Overview

This project solves the problem of disorganized PDF files that are uploaded from mobile scanning apps. Instead of keeping filenames based on scan timestamps, this processor:

1. Monitors a WebDAV folder for new PDF files
2. Extracts text content from PDFs (including OCR)
3. Analyzes the content using OpenRouter AI models
4. Generates meaningful filenames based on document type, date, and summary
5. Saves processed files to an output folder

## Features

- **WebDAV Integration**: Connects to your NAS WebDAV server
- **AI-Powered Analysis**: Uses OpenRouter API with GPT-4o-mini or other models
- **Smart Filename Generation**: Creates descriptive filenames like `2024-05-14_invoice_acme_corp.pdf`
- **Configurable**: Easy to customize through environment variables
- **Continuous Monitoring**: Runs as a daemon, checking for new files at regular intervals

## Prerequisites

- Docker and Docker Compose installed
- Access to a WebDAV server (e.g., Nextcloud, Synology NAS, etc.)
- OpenRouter API key ([get one here](https://openrouter.ai/))

## Configuration

### Environment Variables

Create a `.env` file in the project directory based on `.env.example`:

```bash
# WebDAV Configuration
WEBDAV_URL=http://nas.local/webdav
WEBDAV_USERNAME=your_username
WEBDAV_PASSWORD=your_password

# Folder paths (relative to WebDAV root)
WEBDAV_WATCH_FOLDER=/incoming
WEBDAV_OUTPUT_FOLDER=/processed

# OpenRouter API Configuration
OPENROUTER_API_KEY=your_api_key_here
OPENROUTER_MODEL=openai/gpt-4o-mini

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
| `OPENROUTER_API_KEY` | - | Your OpenRouter API key |
| `OPENROUTER_MODEL` | openai/gpt-4o-mini | AI model to use for analysis |
| `SCAN_DATE_FORMAT` | %Y-%m-%d | Date format for generated filenames |
| `MIN_CONFIDENCE` | 0.6 | Minimum confidence score for processing |
| `FILENAME_PATTERN` | {date}_{type}_{summary}.pdf | Pattern for new filenames |
| `CHECK_INTERVAL` | 60 | Seconds between file checks |
| `LOG_LEVEL` | INFO | Logging level (DEBUG, INFO, WARNING, ERROR) |

### Filename Pattern Placeholders

- `{date}` - Document date or current date
- `{type}` - Document type (invoice, receipt, contract, etc.)
- `{summary}` - Brief summary of document content

## Usage

### Quick Start

1. Clone or copy this repository to your NAS or server

2. Create a `.env` file with your configuration:

```bash
cp .env.example .env
# Edit .env with your settings
```

3. Build and start the container:

```bash
docker-compose build
docker-compose up -d
```

4. Upload PDF files to your WebDAV `/incoming` folder

5. Check the `/processed` folder for renamed files

### View Logs

```bash
# View container logs
docker-compose logs -f

# Or check the log file directly
tail -f logs/pdf-processor.log
```

### Stop the Container

```bash
docker-compose down
```

## AI Model Selection

The processor uses OpenRouter API, which provides access to many AI models. Some recommended models:

- **openai/gpt-4o-mini** (default) - Fast and cost-effective
- **anthropic/claude-3-haiku** - Good for document analysis
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
- Verify OpenRouter API key is correct
- Check API credits/balance on OpenRouter
- Try a different model

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

- Uses [OpenRouter](https://openrouter.ai/) for AI model access
- Built with Python, Docker, and WebDAV
- PDF processing powered by PyPDF2 and pdfplumber
