# ClipForge AI — Product Requirements Document (PRD)

## 1. Executive Summary
ClipForge AI is an autonomous, high-performance desktop-grade SaaS web application built natively for Windows 11. It transforms long-form videos and authorized livestreams into engaging, professionally edited short-form clips, with full human-in-the-loop editing controls and direct social media publishing to YouTube Shorts, Instagram Reels, and Facebook Reels.

## 2. Core Personas & Use Cases
- **Content Creators / Podcasters**: Upload long conversations, automatically extract viral hooks, generate animated subtitles, and publish directly.
- **Livestreamers (Kick / Twitch)**: Monitor stream segments, capture highlights, and queue clips for social platforms.
- **Social Media Managers**: Batch edit metadata (titles, descriptions, hashtags), review video reframing, and manage scheduled publishing.

## 3. Functional Requirements

### 3.1 Media Ingestion & Probing
- Native file upload via multipart chunked upload (MP4, MOV, MKV, WebM).
- Native FFprobe metadata extraction (resolution, duration, codecs, FPS, audio channels).
- Fast thumbnail generation at keyframe positions.
- Low-resolution editing proxies generated in background to ensure 60 FPS timeline scrubbing.

### 3.2 AI Analysis & Moment Discovery
- Audio separation and local transcription (Faster-Whisper).
- Scene detection (PySceneDetect) and visual moment scoring.
- OmniRouter LLM integration for hook analysis, virality scoring (0–100), title/description generation, and hashtag recommendations.
- Non-destructive suggestion storage: AI suggestions never overwrite manual edits without explicit user action.

### 3.3 Complete Professional Video Editor
- **Timeline Controls**: Trim start/end, timeline zoom (1x to 10x), frame stepping, play/pause, playback speed (0.5x, 1x, 1.5x, 2x), interactive scrubber.
- **Visual Transforms**: 9:16 vertical reframe, smart auto-crop, center crop, manual reframing, background blur for letterboxing.
- **Subtitle System**: Word-by-word timing edit, style presets (MrBeast, Neon Glow, Classic Clean, Minimalist), custom colors, font sizes, karaoke highlighting.
- **Audio Controls**: Volume boost, audio normalization, mute, fade in/out.

### 3.4 Complete Metadata & Publishing Controls
- **Title Editor**: Character counter, AI generator (5 variations), reset, manual override.
- **Description & Caption Editor**: Platform-specific multiline descriptions, hashtag injector, character counter.
- **Tags & Hashtag Editor**: Dedicated YouTube keyword tags vs Instagram/Facebook hashtags, duplicate detection, batch copy.
- **Thumbnail Customizer**: Frame grabber, custom image upload, text overlays.
- **Platform-Specific Tabs**: Dedicated UI fields for YouTube Shorts (privacy, tags), Instagram Reels (caption, cover), and Facebook Reels.

### 3.5 Native Background Job Queue
- Durable SQLite-backed job queue with atomic job reservation (`SELECT FOR UPDATE` or SQLite transaction locking).
- Job recovery across app restarts, retry management with exponential backoff, real-time progress percentage (0-100%).
- Graceful cancellation checkpoints.

## 4. Non-Functional Requirements
- **Performance**: Interaction feedback < 100 ms, timeline scrubbing at 60 FPS via proxy, low idle CPU utilization (< 2%).
- **Hardware Target**: Optimized for Intel Core i7 with integrated graphics, 16 GB RAM, native Windows 11. No CUDA requirement.
- **Zero Docker**: Zero containers required for local development or production usage.
