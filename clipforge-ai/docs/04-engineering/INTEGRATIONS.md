# INTEGRATIONS.md

## Overview

ClipForge AI integrates with external services for AI analysis, video hosting, and social media publishing.

## OmniRouter (AI Gateway)

- **Purpose**: Local LLM gateway for viral moment detection, title/description generation, hashtag suggestions
- **Endpoint**: Configurable via `OMNIROUTER_BASE_URL` (default: `http://localhost:11434/v1`)
- **Authentication**: Optional API key via `OMNIROUTER_API_KEY`
- **Status**: Connection tested by health endpoint. Full integration planned for Milestone 3.

## YouTube (Publishing)

- **Purpose**: Upload clips as YouTube Shorts
- **Auth**: Google OAuth 2.0 (`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`)
- **API**: YouTube Data API v3
- **Status**: Planned for Milestone 6

## Instagram Reels (Publishing)

- **Purpose**: Publish clips as Instagram Reels
- **Auth**: Meta OAuth (`META_APP_ID`, `META_APP_SECRET`)
- **API**: Instagram Graph API
- **Status**: Planned for Milestone 6

## Facebook Reels (Publishing)

- **Purpose**: Publish clips as Facebook Reels
- **Auth**: Meta OAuth (shared with Instagram)
- **API**: Facebook Graph API
- **Status**: Planned for Milestone 6

## Faster-Whisper (Transcription)

- **Purpose**: Local speech-to-text transcription
- **Implementation**: Python library, runs on CPU
- **Status**: Planned for Milestone 3

## Current Integration Status

| Service | Status | Milestone |
|---------|--------|-----------|
| OmniRouter | Health check only | M1 ✅ |
| FFmpeg/FFprobe | Health check only | M1 ✅ |
| Faster-Whisper | Not started | M3 |
| YouTube API | Not started | M6 |
| Instagram API | Not started | M6 |
| Facebook API | Not started | M6 |

---
*Integration implementations will be added in their respective milestones.*
