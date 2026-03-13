# Portrait Generator: AI Smart-Crop & Video Pipeline

A complete video pipeline to convert landscape videos (YouTube or local) into vertical portrait format with AI-powered features:
- **Smart Crop**: Automatically follows the active speaker using YOLOv8.
- **AI Transcription**: High-quality transcription via Sumopod AI (Whisper).
- **Topic Analysis**: AI identifies viral topics/highlights for clipping.
- **Auto-Clipping**: Automatically generates portrait clips for each identified topic.

## 🚀 Quick Start with Docker

The easiest way to run the Portrait Generator is using Docker.

### 1. Prerequisites
- [Docker](https://www.docker.com/products/docker-desktop/)
- [Docker Compose](https://docs.docker.com/compose/install/)

### 2. Setup
1. Clone this repository.
2. Setup your environment variables:
   ```bash
   cp env.example .env
   ```
3. Edit the `.env` file and add your `SUMOPOD_API_KEY`.

### 3. Run
You can either build locally or pull the latest pre-built image from GitHub Container Registry (GHCR):

**Option A: Run latest pre-built image (Recommended)**
```bash
docker-compose pull
docker-compose up -d
```

**Option B: Build locally**
```bash
docker-compose up -d --build
```

The system will be available at:
- **API**: `http://localhost:8081` (Proxied via Nginx)
- **Direct API Output**: `http://localhost:8000`
- **Log Monitor UI**: `http://localhost:8081/logs-ui`

## 🔄 CI/CD & Auto-Build

This repository is equipped with **GitHub Actions**. Every time you push code to the `main` branch:
1. GitHub automatically builds a new Docker image.
2. The image is pushed to **GitHub Container Registry (GHCR)**.
3. You can update your server just by running `docker-compose pull && docker-compose up -d`.

## 🛠 Features

- **Stage 1 (Analysis)**: Downloads video, extracts audio, transcribes with AI, and analyzes topics.
- **Stage 2 (Clipping)**: Smart-crops the video based on the speaker and burns subtitles automatically.
- **Nginx Proxy**: Serves generated video files efficiently and provides a secure API entry point.

## 📖 API Documentation

See [API_GUIDE.md](API_GUIDE.md) for full endpoint details and integration examples.

## 📦 Project Structure

```
.
├── app.py                # FastAPI Main Application
├── smartcrop/            # Core clipping & detection logic
├── nginx/                # Nginx configuration (Reverse Proxy)
├── scripts/              # Utility & deployment scripts
├── tests/                # Verification & test scripts
├── data/                 # Database and logs (Mounted volume)
├── output/               # Rendered video files (Mounted volume)
├── Dockerfile            # App container definition
└── docker-compose.yml    # Full stack definition
```

---
*Powered by Sumopod AI & SmartCrop Engine.*
