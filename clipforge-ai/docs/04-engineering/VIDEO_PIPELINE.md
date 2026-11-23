# VIDEO_PIPELINE.md

## Overview

The video processing pipeline uses FFmpeg and FFprobe for all media operations. This document describes the planned pipeline architecture.

## Pipeline Stages

### 1. Ingestion
- Accept uploaded video files (MP4, MOV, MKV, WEBM)
- Validate MIME type and file size against `MAX_UPLOAD_SIZE_MB`
- Run `ffprobe` to extract metadata: duration, resolution, codec, frame rate, audio channels

### 2. Thumbnail Generation
- Extract a frame at ~10% of duration using FFmpeg
- Scale to 640×360 for dashboard preview
- Store in `storage/thumbnails/`

### 3. Audio Extraction
- Extract audio track to WAV (16kHz mono) for transcription
- Store temporarily in `storage/temp/`

### 4. Clip Generation
- Given start/end timestamps, extract segment using FFmpeg
- Apply smart crop to 9:16 (1080×1920) for vertical format
- Re-encode: H.264, AAC, 30 FPS
- Support 720p, 1080p, 1440p, 4K export resolutions

### 5. Caption Overlay
- Burn subtitles onto video using FFmpeg `drawtext` or ASS filter
- Support multiple caption presets (font, position, animation)

### 6. Output
- Store final clips in `storage/clips/`
- Generate preview thumbnails

## FFmpeg Configuration

```
# Default output settings
Resolution: 1080x1920 (9:16)
Codec: H.264 (libx264)
Audio: AAC 128kbps
FPS: 30
Preset: medium (CPU-optimized)
```

## Processing Constraints

- Single render worker by default (`MAX_RENDER_WORKERS=1`)
- Chunked processing for large files to stay within 16GB RAM
- Low-resolution previews generated first for UI responsiveness
- CPU-first execution (no CUDA/GPU requirement)

## Current Status

**Milestone 1**: Pipeline interfaces defined. No actual video processing implemented yet.

FFmpeg availability is checked by the health endpoint (`GET /api/v1/health/dependencies`).

---
*Detailed implementation will be added in Milestone 4 (Rendering).*
