'use client';

import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  LayoutDashboard,
  Film,
  Scissors,
  Sparkles,
  Send,
  ListTodo,
  Settings,
  Upload,
  Play,
  Pause,
  RotateCcw,
  Volume2,
  VolumeX,
  Clock,
  Maximize2,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  Sliders,
  Type,
  Hash,
  Share2,
  Video,
  Camera,
  Globe,
  ChevronRight,
  Eye,
  Trash2,
  Plus,
  Layers,
  Zap,
} from 'lucide-react';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const OMNI_URL = process.env.NEXT_PUBLIC_OMNIROUTER_URL || 'http://localhost:20128/v1';

// --- Type Definitions ---
interface HealthDependencies {
  database?: { status: string; backend?: string };
  ffmpeg?: { status: string; version?: string };
  omnirouter?: { status: string; url?: string };
  worker?: { status: string; active_worker_id?: string; queue_stats?: any };
}

interface VideoItem {
  id: number;
  filename: string;
  duration: number;
  resolution: string;
  fps: number;
  status: string;
  thumbnail_path?: string;
  proxy_path?: string;
  clip_count: number;
  created_at: string;
}

interface ClipItem {
  output_path?: string;
  id: number;
  video_id: number;
  title: string;
  hook_text?: string;
  description?: string;
  youtube_tags?: string;
  social_hashtags?: string;
  start_time: number;
  end_time: number;
  duration: number;
  viral_score: number;
  explanation?: string;
  aspect_ratio: string;
  crop_x?: number;
  crop_y?: number;
  crop_zoom?: number;
  caption_preset: string;
  caption_color?: string;
  caption_highlight_color?: string;
  caption_font_size?: number;
  status: string;
}

interface JobItem {
  id: string;
  queue: string;
  task_type: string;
  status: string;
  progress: number;
  progress_message: string;
  error_message?: string | null;
  priority: number;
  created_at: string;
}

export default function ClipForgeApp() {
  const [activeTab, setActiveTab] = useState<'dashboard' | 'library' | 'editor' | 'metadata' | 'queue' | 'settings'>('dashboard');

  // Backend state
  const [deps, setDeps] = useState<HealthDependencies | null>(null);
  const [apiConnected, setApiConnected] = useState<boolean>(false);
  const [omniConnected, setOmniConnected] = useState<boolean>(false);
  const [videos, setVideos] = useState<VideoItem[]>([]);
  const [clips, setClips] = useState<ClipItem[]>([]);
  const [jobs, setJobs] = useState<JobItem[]>([]);
  const [selectedVideo, setSelectedVideo] = useState<VideoItem | null>(null);
  const [selectedClip, setSelectedClip] = useState<ClipItem | null>(null);

  // Editor states
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [currentTime, setCurrentTime] = useState<number>(0);
  const [timelineZoom, setTimelineZoom] = useState<number>(1);
  const [aspectRatio, setAspectRatio] = useState<string>('9:16');
  const [cropX, setCropX] = useState<number>(50);
  const [cropY, setCropY] = useState<number>(50);
  const [cropZoom, setCropZoom] = useState<number>(1.0);
  const [captionPreset, setCaptionPreset] = useState<string>('mrbeast');
  const [captionFontSize, setCaptionFontSize] = useState<number>(44);
  const [captionColor, setCaptionColor] = useState<string>('#FFFFFF');
  const [captionHighlightColor, setCaptionHighlightColor] = useState<string>('#FACC15');
  const [trimStart, setTrimStart] = useState<number>(0);
  const [trimEnd, setTrimEnd] = useState<number>(30);
  const [playbackSpeed, setPlaybackSpeed] = useState<number>(1);
  const [isMuted, setIsMuted] = useState<boolean>(false);
  const [blurBackground, setBlurBackground] = useState<boolean>(true);

  // Metadata states
  const [metaPlatform, setMetaPlatform] = useState<'youtube' | 'instagram' | 'facebook'>('youtube');
  const [metaTitle, setMetaTitle] = useState<string>('The Hidden Hack That Changes Everything');
  const [metaDescription, setMetaDescription] = useState<string>('Discover how top creators produce 10x more content without extra effort.\n\n#shorts #creatorhacks #productivity');
  const [metaHook, setMetaHook] = useState<string>('Wait until you see how this changes everything...');
  const [metaYoutubeTags, setMetaYoutubeTags] = useState<string>('shorts, viral, productivity, creator tips');
  const [metaHashtags, setMetaHashtags] = useState<string>('#shorts #viral #growthtips #productivity');
  const [metaPrivacy, setMetaPrivacy] = useState<string>('public');
  const [saveSuccessNotice, setSaveSuccessNotice] = useState<string | null>(null);

  // Upload simulation/state
  const [renderedClips, setRenderedClips] = useState<Pick<ClipItem, "id" | "title" | "output_path">[]>([]);
  const [quality, setQuality] = useState("best");
  const [clipMode, setClipMode] = useState<'ai' | 'transcript'>('ai');
  const [importUrl, setImportUrl] = useState("");
  const [importMessage, setImportMessage] = useState("");
  const [creatorUrl, setCreatorUrl] = useState("");
  const [monitorMessage, setMonitorMessage] = useState("");
  const [monitors, setMonitors] = useState<Array<{
    id: string; url: string; paused: boolean; next_run_at: string | null;
    last_poll: { at: string; queued?: number; error?: string } | null;
  }>>([]);
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [uploadProgress, setUploadProgress] = useState<number>(0);

  // Poll backend health and data
  const fetchData = useCallback(async () => {
    try {
      const depRes = await fetch(`${API_URL}/api/v1/health/dependencies`);
      if (depRes.ok) {
        const depData = await depRes.json();
        setDeps(depData);
        setApiConnected(true);
        setOmniConnected(depData.omnirouter?.status === 'ok');
      } else {
        setApiConnected(false);
      }

      const vRes = await fetch(`${API_URL}/api/v1/videos`);
      if (vRes.ok) {
        const vData = await vRes.json();
        setVideos(vData);
        if (vData.length > 0 && !selectedVideo) {
          setSelectedVideo(vData[0]);
        }
      }

      const monitorResponse = await fetch(API_URL + '/api/v1/monitors');
      if (monitorResponse.ok) setMonitors(await monitorResponse.json());
      const rendered = await fetch(API_URL + '/api/v1/clips');
      if (rendered.ok) setRenderedClips(await rendered.json());
      const jRes = await fetch(`${API_URL}/api/v1/jobs`);
      if (jRes.ok) {
        const jData = await jRes.json();
        setJobs(jData);
      }
    } catch (e) {
      setApiConnected(false);
    }
  }, [selectedVideo]);

  useEffect(() => {
    fetchData();
    const timer = setInterval(fetchData, 4000);
    return () => clearInterval(timer);
  }, [fetchData]);

  function loadClip(clip: ClipItem | null) {
    setSelectedClip(clip);
    if (!clip) return;
    setTrimStart(clip.start_time);
    setTrimEnd(clip.end_time);
    setCropX(Math.round((clip.crop_x ?? 0.5) * 100));
    setCropY(Math.round((clip.crop_y ?? 0.5) * 100));
    setCropZoom(clip.crop_zoom ?? 1);
    setMetaTitle(clip.title);
    setMetaHook(clip.hook_text || '');
    setMetaDescription(clip.description || '');
    setMetaYoutubeTags(clip.youtube_tags || '');
    setMetaHashtags(clip.social_hashtags || '');
  }

  useEffect(() => {
    if (!selectedVideo || activeTab !== 'editor') return;
    let obsolete = false;
    setClips([]);
    loadClip(null);
    fetch(`${API_URL}/api/v1/videos/${selectedVideo.id}/clips`)
      .then(res => res.ok ? res.json() : [])
      .then((data: ClipItem[]) => {
        if (!obsolete) { setClips(data); loadClip(data[0] ?? null); }
      })
      .catch(() => { if (!obsolete) setSaveSuccessNotice('Could not load clips.'); });
    return () => { obsolete = true; };
  }, [selectedVideo, activeTab]);

  // Handle Mock Upload
  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    setUploadProgress(20);

    const formData = new FormData();
    formData.append('file', file);

    try {
      setUploadProgress(60);
      const res = await fetch(`${API_URL}/api/v1/videos/upload`, {
        method: 'POST',
        body: formData,
      });
      setUploadProgress(100);
      if (res.ok) {
        await fetchData();
        setActiveTab('library');
      }
    } catch (err) {
      console.error(err);
    } finally {
      setIsUploading(false);
      setUploadProgress(0);
    }
  };

  // Trigger AI Moment Analysis
  const handleAnalyzeMoments = async (videoId: number) => {
    try {
      const res = await fetch(`${API_URL}/api/v1/videos/${videoId}/analyze?mode=${clipMode}`, { method: 'POST' });
      if (res.ok) {
        setActiveTab('queue');
        await fetchData();
      }
    } catch (err) {
      console.error(err);
    }
  };

  // Save Clip Edits
  const handleSaveClipEdits = async () => {
    if (!selectedClip) return;
    try {
      const res = await fetch(`${API_URL}/api/v1/clips/${selectedClip.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: jsonSafeStringify({
          title: metaTitle,
          hook_text: metaHook,
          description: metaDescription,
          youtube_tags: metaYoutubeTags,
          social_hashtags: metaHashtags,
          start_time: trimStart,
          end_time: trimEnd,
          aspect_ratio: aspectRatio,
          crop_x: cropX / 100,
          crop_y: cropY / 100,
          crop_zoom: cropZoom,
          caption_preset: captionPreset,
          caption_color: captionColor,
          caption_highlight_color: captionHighlightColor,
          caption_font_size: captionFontSize,
        }),
      });
      if (res.ok) {
        setSaveSuccessNotice('All edits persisted to SQLite database!');
        return true;
      }
      const error = await res.json();
      setSaveSuccessNotice(typeof error.detail === 'string' ? error.detail : 'Could not save clip edits.');
    } catch {
      setSaveSuccessNotice('Could not reach the API to save clip edits.');
    }
    return false;
  };

  // Render Clip
  const handleRenderClip = async () => {
    if (!selectedClip || !await handleSaveClipEdits()) return;
    try {
      const res = await fetch(`${API_URL}/api/v1/clips/${selectedClip.id}/render`, { method: 'POST' });
      if (res.ok) {
        setActiveTab('queue');
        await fetchData();
      }
    } catch (e) {
      console.error(e);
    }
  };

  // AI Suggestion Assistant
  const handleGenerateAISuggestions = async (action: string) => {
    if (!selectedClip) return;
    try {
      const res = await fetch(`${API_URL}/api/v1/clips/${selectedClip.id}/ai-suggestions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action,
          target_platform: metaPlatform === 'youtube' ? 'youtube_shorts' : 'instagram_reels',
          current_title: metaTitle,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        if (data.suggestions && data.suggestions.length > 0) {
          if (action === 'generate_titles') setMetaTitle(data.suggestions[0]);
          if (action === 'improve_hook') setMetaHook(data.suggestions[0]);
        }
        if (data.hashtags) setMetaHashtags(data.hashtags);
        if (data.youtube_tags) setMetaYoutubeTags(data.youtube_tags);
      }
    } catch (e) {
      console.error(e);
    }
  };

  function jsonSafeStringify(obj: any) {
    return JSON.stringify(obj);
  }

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[#0a0b0e] text-slate-100 antialiased select-none">
      {/* ── Left Sidebar ────────────────────────────────────────── */}
      <aside className="w-64 border-r border-white/5 bg-[#101217] flex flex-col justify-between shrink-0">
        <div>
          {/* Brand */}
          <div className="flex items-center gap-3 px-6 py-5 border-b border-white/5">
            <div className="h-9 w-9 rounded-xl bg-gradient-to-tr from-violet-600 via-indigo-500 to-blue-500 flex items-center justify-center shadow-lg shadow-violet-500/20">
              <Zap className="h-5 w-5 text-white" />
            </div>
            <div>
              <span className="font-bold tracking-tight text-white text-base">ClipForge AI</span>
              <div className="flex items-center gap-1.5 mt-0.5">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400"></span>
                <span className="text-[11px] font-medium text-slate-400">Windows Native</span>
              </div>
            </div>
          </div>

          {/* Navigation Items */}
          <nav className="p-3 space-y-1">
            {[
              { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
              { id: 'library', label: 'Video Library', icon: Film, count: videos.length },
              { id: 'editor', label: 'Clip Editor', icon: Scissors },
              { id: 'queue', label: 'Job Monitor', icon: ListTodo, count: jobs.filter((j) => j.status === 'running').length },
              { id: 'settings', label: 'Settings', icon: Settings },
            ].map((item) => {
              const Icon = item.icon;
              const isActive = activeTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => setActiveTab(item.id as any)}
                  className={`w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl text-sm font-medium transition-all ${
                    isActive
                      ? 'bg-violet-600/15 text-violet-300 border border-violet-500/25 shadow-inner'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-white/5'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <Icon className={`h-4 w-4 ${isActive ? 'text-violet-400' : 'text-slate-400'}`} />
                    <span>{item.label}</span>
                  </div>
                  {item.count !== undefined && item.count > 0 && (
                    <span className="px-2 py-0.5 text-[11px] rounded-full bg-white/10 text-slate-300 font-semibold">
                      {item.count}
                    </span>
                  )}
                </button>
              );
            })}
          </nav>
        </div>

        {/* System Pill Footer */}
        <div className="p-4 border-t border-white/5 bg-[#0d0e13]">
          <div className="flex items-center justify-between text-xs text-slate-400 mb-2">
  <span className="flex items-center gap-1.5">
    <span className={`h-2 w-2 rounded-full ${apiConnected ? 'bg-emerald-500' : 'bg-rose-500 animate-pulse'}`}></span>
    FastAPI {apiConnected ? 'Online' : 'Offline'}
  </span>
  <span className="flex items-center gap-1.5">
    <span className={`h-2 w-2 rounded-full ${omniConnected ? 'bg-emerald-500' : 'bg-rose-500 animate-pulse'}`}></span>
    OmniRouter {omniConnected ? 'Online' : 'Offline'}
  </span>
  <span className="font-mono text-[10px] text-slate-500">v0.2.0</span>
</div>
          <div className="text-[11px] text-slate-500 leading-tight">
            SQLite WAL Mode • Zero Docker Required
          </div>
        </div>
      </aside>

      {/* ── Main Content Area ───────────────────────────────────── */}
      <main className="flex-1 flex flex-col overflow-hidden bg-[#0a0b0e]">
        {/* Header Bar */}
        <header className="h-14 border-b border-white/5 px-8 flex items-center justify-between shrink-0 bg-[#0d0f14]/80 backdrop-blur">
          <div className="flex items-center gap-3">
            <h1 className="font-semibold text-white capitalize text-sm tracking-wide">
              {activeTab === 'metadata' ? 'Metadata & AI Studio' : activeTab}
            </h1>
            {selectedVideo && activeTab === 'editor' && (
              <span className="text-xs px-2.5 py-1 rounded-md bg-white/5 border border-white/10 text-slate-300">
                Media: {selectedVideo.filename}
              </span>
            )}
          </div>

          <div className="flex items-center gap-3">
            {saveSuccessNotice && (
              <span className="text-xs text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-3 py-1 rounded-lg flex items-center gap-1.5">
                <CheckCircle2 className="h-3.5 w-3.5" /> {saveSuccessNotice}
              </span>
            )}

            <label className="cursor-pointer flex items-center gap-2 bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white text-xs font-medium px-3.5 py-1.5 rounded-lg shadow-sm transition">
              <Upload className="h-3.5 w-3.5" />
              <span>Import Video</span>
              <input type="file" accept="video/*" className="hidden" onChange={handleUpload} disabled={isUploading} />
            </label>
          </div>
        </header>

        {/* View Switcher */}
        <div className="flex-1 overflow-y-auto p-8">
          {/* ── TAB 1: DASHBOARD ──────────────────────────────────── */}
          {activeTab === 'dashboard' && (
            <div className="max-w-6xl mx-auto space-y-8">
              {/* Quick KPI Cards */}
              <div className="grid grid-cols-4 gap-4">
                {[
                  { label: 'Imported Videos', val: videos.length, icon: Film, color: 'text-blue-400' },
                  { label: 'Clips in Library', val: videos.reduce((total, video) => total + video.clip_count, 0), icon: Scissors, color: 'text-violet-400' },
                  { label: 'Active Queue Jobs', val: jobs.filter((j) => j.status === 'running' || j.status === 'queued').length, icon: ListTodo, color: 'text-amber-400' },
                  { label: 'Published / Scheduled', val: 0, icon: Send, color: 'text-emerald-400' },
                ].map((stat, i) => {
                  const Icon = stat.icon;
                  return (
                    <div key={i} className="p-5 rounded-2xl bg-[#12141c] border border-white/5 flex items-center justify-between">
                      <div>
                        <span className="text-xs text-slate-400 font-medium block">{stat.label}</span>
                        <span className="text-2xl font-bold text-white mt-1 block">{stat.val}</span>
                      </div>
                      <div className={`p-3 rounded-xl bg-white/5 ${stat.color}`}>
                        <Icon className="h-5 w-5" />
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* System Dependencies Status */}
              <div className="p-6 rounded-2xl bg-[#12141c] border border-white/5 space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2.5">
                    <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                    <h2 className="text-sm font-semibold text-white">Native Windows System Dependencies</h2>
                  </div>
                  <button onClick={fetchData} className="text-xs text-slate-400 hover:text-white flex items-center gap-1.5 transition">
                    <RefreshCw className="h-3 w-3" /> Refresh Status
                  </button>
                </div>

                <div className="grid grid-cols-4 gap-4 pt-2">
                  {[
                    { name: 'FastAPI Backend', ok: apiConnected, detail: 'Uvicorn 127.0.0.1:8000' },
                    { name: 'SQLite Database', ok: deps?.database?.status === 'ok', detail: 'WAL mode enabled' },
                    { name: 'FFmpeg / FFprobe', ok: deps?.ffmpeg?.status === 'ok', detail: deps?.ffmpeg?.status === 'ok' ? 'Available in PATH' : 'Optional for M1' },
                    { name: 'Local OmniRouter AI', ok: deps?.omnirouter?.status === 'ok', detail: deps?.omnirouter?.status === 'ok' ? 'Connected' : 'localhost:20128' },
                  ].map((d, i) => (
                    <div key={i} className="p-4 rounded-xl bg-[#181a24] border border-white/5">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-xs font-semibold text-slate-200">{d.name}</span>
                        <span className={`h-2 w-2 rounded-full ${d.ok ? 'bg-emerald-400' : 'bg-amber-400'}`}></span>
                      </div>
                      <span className="text-[11px] text-slate-400 block">{d.detail}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Quick Actions / Getting Started */}
              <div className="grid grid-cols-2 gap-6">
                <div className="p-6 rounded-2xl bg-[#12141c] border border-white/5 flex flex-col justify-between">
                  <div>
                    <h3 className="text-sm font-semibold text-white mb-2">AI Clip Generation Flow</h3>
                    <p className="text-xs text-slate-400 leading-relaxed">
                      1. Upload an MP4 video.<br />
                      2. Click &quot;Analyze Moments&quot; to discover hooks.<br />
                      3. Frame-accurately trim and reframe to vertical 9:16.<br />
                      4. Preview or download your captioned clips.
                    </p>
                  </div>
                  <div className="pt-6 flex gap-3">
                    <button
                      onClick={() => setActiveTab('library')}
                      className="px-4 py-2 rounded-xl bg-violet-600 hover:bg-violet-500 text-white text-xs font-medium transition"
                    >
                      Open Video Library
                    </button>
                    <button
                      onClick={() => setActiveTab('editor')}
                      className="px-4 py-2 rounded-xl bg-white/5 hover:bg-white/10 text-slate-300 text-xs font-medium transition"
                    >
                      Open Clip Editor
                    </button>
                  </div>
                </div>

                <div className="p-6 rounded-2xl bg-[#12141c] border border-white/5 flex flex-col justify-between">
                  <div>
                    <h3 className="text-sm font-semibold text-white mb-2">Durable Media Processing Queue</h3>
                    <p className="text-xs text-slate-400 leading-relaxed">
                      Background rendering and moment analysis run on a persistent, crash-resilient SQLite queue.
                      Tasks recover seamlessly across application restarts.
                    </p>
                  </div>
                  <div className="pt-6">
                    <button
                      onClick={() => setActiveTab('queue')}
                      className="px-4 py-2 rounded-xl bg-white/5 hover:bg-white/10 text-slate-300 text-xs font-medium transition"
                    >
                      View Live Queue Monitor
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* ── TAB 2: VIDEO LIBRARY ──────────────────────────────── */}
          {activeTab === 'library' && (
            <div className="max-w-6xl mx-auto space-y-6">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-base font-semibold text-white">Imported Source Media</h2>
                  <p className="text-xs text-slate-400 mt-0.5">Manage source videos and generate candidate moments</p>
                </div>
                <label className="cursor-pointer flex items-center gap-2 bg-violet-600 hover:bg-violet-500 text-white text-xs font-medium px-4 py-2 rounded-xl shadow-sm transition">
                  <Plus className="h-4 w-4" />
                  <span>Upload Long-Form Video</span>
                  <input type="file" accept="video/*" className="hidden" onChange={handleUpload} />
                </label>
              </div>

              <form className="flex flex-wrap gap-3" onSubmit={async event => {
                event.preventDefault();
                try {
                  const response = await fetch(API_URL + '/api/v1/videos/import', {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({url: importUrl, quality, mode: clipMode})
                  });
                  const data = await response.json();
                  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Invalid recording URL');
                  setImportMessage(data.status === 'completed' ? 'Already imported' : 'Import queued');
                  setActiveTab('queue');
                  await fetchData();
                } catch (error) { setImportMessage(String(error)); }
              }}>
                <input type="url" required aria-label="Recording URL" placeholder="YouTube video or Kick VOD URL" className="flex-1 rounded bg-slate-900 p-2" value={importUrl} onChange={e => setImportUrl(e.target.value)} />
                <select aria-label="Import and export quality" className="rounded bg-slate-900 p-2" value={quality} onChange={e => setQuality(e.target.value)}><option value="best">Best quality</option><option value="balanced">Balanced (up to 1080p)</option><option value="fast">Fast (up to 720p)</option></select>
                <select aria-label="Highlight selection" className="rounded bg-slate-900 p-2" value={clipMode} onChange={event => setClipMode(event.target.value === 'transcript' ? 'transcript' : 'ai')}>
                  <option value="ai">OmniRouter AI highlights</option>
                  <option value="transcript">Transcript excerpt (offline, not AI)</option>
                </select>
                <button className="rounded bg-violet-600 px-4">Generate clips</button>
                <span role="status">{importMessage}</span>
              </form>
              {renderedClips.map(c => <article key={c.id}>
                <h3>{c.title}</h3><video controls preload="metadata" className="max-h-80" src={API_URL + c.output_path!}/>
                <a download href={API_URL + "/api/v1/clips/" + c.id + "/download"}>Download MP4</a></article>)}
              {videos.length === 0 ? (
                <div className="border border-dashed border-white/10 rounded-2xl p-16 text-center space-y-4 bg-[#12141c]/50">
                  <div className="h-12 w-12 rounded-2xl bg-white/5 flex items-center justify-center mx-auto text-slate-400">
                    <Film className="h-6 w-6" />
                  </div>
                  <div>
                    <h3 className="text-sm font-semibold text-white">No videos imported yet</h3>
                    <p className="text-xs text-slate-400 mt-1">Upload an MP4, MOV, or WebM video to get started</p>
                  </div>
                  <label className="cursor-pointer inline-flex items-center gap-2 bg-white/10 hover:bg-white/15 text-white text-xs font-medium px-4 py-2 rounded-xl transition">
                    <Upload className="h-4 w-4" /> Browse File
                    <input type="file" accept="video/*" className="hidden" onChange={handleUpload} />
                  </label>
                </div>
              ) : (
                <div className="grid grid-cols-3 gap-5">
                  {videos.map((vid) => (
                    <div
                      key={vid.id}
                      className={`p-4 rounded-2xl bg-[#12141c] border transition-all ${
                        selectedVideo?.id === vid.id ? 'border-violet-500/50 shadow-md shadow-violet-500/5' : 'border-white/5 hover:border-white/15'
                      }`}
                    >
                      <div className="h-36 rounded-xl bg-[#181a24] flex items-center justify-center relative overflow-hidden mb-3 border border-white/5">
                        {vid.thumbnail_path ? (
                          <img
                            src={`${API_URL}${vid.thumbnail_path}`}
                            alt={vid.filename}
                            className="w-full h-full object-cover"
                          />
                        ) : (
                          <Film className="h-8 w-8 text-slate-500" />
                        )}
                        <span className="absolute bottom-2 right-2 text-[10px] font-mono px-1.5 py-0.5 rounded bg-black/70 text-slate-300">
                          {vid.resolution}
                        </span>
                      </div>

                      <h4 className="text-xs font-semibold text-white truncate" title={vid.filename}>
                        {vid.filename}
                      </h4>
                      <div className="flex items-center justify-between text-[11px] text-slate-400 mt-2">
                        <span>Duration: {Math.round(vid.duration)}s</span>
                        <span className="px-2 py-0.5 rounded-full bg-violet-500/10 text-violet-300 border border-violet-500/20">
                          {vid.clip_count} clips
                        </span>
                      </div>

                      <div className="grid grid-cols-2 gap-2 mt-4">
                        <button
                          onClick={() => handleAnalyzeMoments(vid.id)}
                          className="flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-lg bg-violet-600 hover:bg-violet-500 text-white text-[11px] font-medium transition"
                        >
                          <Sparkles className="h-3 w-3" /> Analyze
                        </button>
                        <button
                          onClick={() => {
                            setSelectedVideo(vid);
                            setActiveTab('editor');
                          }}
                          className="flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-slate-300 text-[11px] font-medium transition"
                        >
                          <Scissors className="h-3 w-3" /> Edit
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* ── TAB 3: PROFESSIONAL CLIP EDITOR ───────────────────── */}
          {activeTab === 'editor' && (
            <div className="mx-auto max-w-4xl space-y-4 rounded-xl border border-white/10 bg-[#12141c] p-5">
              <h2 className="text-lg font-semibold">Clip editor</h2>
              <label className="block">Source <select className="bg-slate-900 p-2" value={selectedVideo?.id ?? ''} onChange={event => setSelectedVideo(videos.find(video => video.id === Number(event.target.value)) ?? null)}>
                <option value="">Select a source</option>{videos.map(video => <option key={video.id} value={video.id}>{video.filename}</option>)}
              </select></label>
              <label className="block">Clip <select className="bg-slate-900 p-2" value={selectedClip?.id ?? ''} onChange={event => loadClip(clips.find(clip => clip.id === Number(event.target.value)) ?? null)}>
                <option value="">Select a clip</option>{clips.map(clip => <option key={clip.id} value={clip.id}>{clip.title}</option>)}
              </select></label>
              {selectedClip ? <>
                {selectedClip.output_path && <>
                  <p className="text-sm text-slate-400">Last rendered clip. Render again to preview edits.</p>
                  <video controls preload="metadata" className="max-h-96" src={API_URL + selectedClip.output_path} />
                  <a className="block underline" href={`${API_URL}/api/v1/clips/${selectedClip.id}/download`}>Download MP4</a>
                </>}
                <div className="flex flex-wrap gap-4">
                  <label>Trim start (s) <input className="w-24 bg-slate-900 p-1" type="number" min="0" step="0.01" value={trimStart} onChange={e => setTrimStart(Number(e.target.value))} /></label>
                  <label>Trim end (s) <input className="w-24 bg-slate-900 p-1" type="number" min="0" step="0.01" value={trimEnd} onChange={e => setTrimEnd(Number(e.target.value))} /></label>
                </div>
                <label className="block">Crop horizontal ({cropX}%) <input type="range" min="0" max="100" value={cropX} onChange={e => setCropX(Number(e.target.value))} /></label>
                <label className="block">Crop vertical ({cropY}%) <input type="range" min="0" max="100" value={cropY} onChange={e => setCropY(Number(e.target.value))} /></label>
                <label className="block">Zoom ({cropZoom}x) <input type="range" min="1" max="2.5" step="0.1" value={cropZoom} onChange={e => setCropZoom(Number(e.target.value))} /></label>
                <p className="text-xs text-slate-400">Captions use timed transcription. Caption text and style editing are not available here.</p>
                <div className="flex gap-3">
                  <button className="rounded bg-slate-700 p-2" onClick={handleSaveClipEdits}>Save changes</button>
                  <button className="rounded bg-violet-600 p-2" onClick={handleRenderClip}>Save and re-render</button>
                </div>
                <p role="status">{saveSuccessNotice}</p>
              </> : <p>Generate a clip from the Video Library first.</p>}
            </div>
          )}

          {/* ── TAB 4: METADATA & AI STUDIO ───────────────────────── */}
          {activeTab === 'metadata' && (
            <div className="max-w-4xl mx-auto space-y-6">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-base font-semibold text-white">Clip Publishing & Metadata Studio</h2>
                  <p className="text-xs text-slate-400 mt-0.5">Customize viral titles, platform-specific descriptions, tags, and hooks</p>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => handleGenerateAISuggestions('generate_titles')}
                    className="px-3 py-1.5 rounded-lg bg-violet-600/20 text-violet-300 border border-violet-500/30 hover:bg-violet-600/30 text-xs font-medium flex items-center gap-1.5 transition"
                  >
                    <Sparkles className="h-3 w-3" /> AI Titles
                  </button>
                  <button
                    onClick={() => handleGenerateAISuggestions('generate_hashtags')}
                    className="px-3 py-1.5 rounded-lg bg-indigo-600/20 text-indigo-300 border border-indigo-500/30 hover:bg-indigo-600/30 text-xs font-medium flex items-center gap-1.5 transition"
                  >
                    <Hash className="h-3 w-3" /> AI Hashtags
                  </button>
                </div>
              </div>

              {/* Platform Selector Tabs */}
              <div className="flex border-b border-white/10">
                {[
                  { id: 'youtube', label: 'YouTube Shorts', icon: Video },
                  { id: 'instagram', label: 'Instagram Reels', icon: Camera },
                  { id: 'facebook', label: 'Facebook Reels', icon: Globe },
                ].map((p) => {
                  const Icon = p.icon;
                  return (
                    <button
                      key={p.id}
                      onClick={() => setMetaPlatform(p.id as any)}
                      className={`flex items-center gap-2 px-6 py-3 text-xs font-semibold border-b-2 transition ${
                        metaPlatform === p.id
                          ? 'border-violet-500 text-white'
                          : 'border-transparent text-slate-400 hover:text-slate-200'
                      }`}
                    >
                      <Icon className="h-4 w-4" />
                      <span>{p.label}</span>
                    </button>
                  );
                })}
              </div>

              {/* Title Editor */}
              <div className="p-5 rounded-2xl bg-[#12141c] border border-white/5 space-y-3">
                <div className="flex justify-between items-center">
                  <label className="text-xs font-semibold text-slate-200 flex items-center gap-2">
                    <Type className="h-4 w-4 text-violet-400" /> Title
                  </label>
                  <span className={`text-[11px] font-mono ${metaTitle.length > 90 ? 'text-amber-400' : 'text-slate-500'}`}>
                    {metaTitle.length} / 100 characters
                  </span>
                </div>
                <input
                  type="text"
                  value={metaTitle}
                  onChange={(e) => setMetaTitle(e.target.value)}
                  className="w-full px-4 py-2.5 rounded-xl bg-[#181a24] border border-white/10 text-white text-sm focus:outline-none focus:border-violet-500 transition"
                  placeholder="Enter a viral, click-worthy hook title..."
                />
              </div>

              {/* Opening Hook Overlay */}
              <div className="p-5 rounded-2xl bg-[#12141c] border border-white/5 space-y-3">
                <div className="flex justify-between items-center">
                  <label className="text-xs font-semibold text-slate-200 flex items-center gap-2">
                    <Zap className="h-4 w-4 text-amber-400" /> Opening Hook Overlay (First 3 Seconds)
                  </label>
                  <button
                    onClick={() => handleGenerateAISuggestions('improve_hook')}
                    className="text-[11px] text-violet-400 hover:underline flex items-center gap-1"
                  >
                    <Sparkles className="h-3 w-3" /> Improve Hook
                  </button>
                </div>
                <input
                  type="text"
                  value={metaHook}
                  onChange={(e) => setMetaHook(e.target.value)}
                  className="w-full px-4 py-2.5 rounded-xl bg-[#181a24] border border-white/10 text-white text-sm focus:outline-none focus:border-violet-500 transition"
                  placeholder="Text overlay displayed prominently during opening seconds..."
                />
              </div>

              {/* Description Editor */}
              <div className="p-5 rounded-2xl bg-[#12141c] border border-white/5 space-y-3">
                <div className="flex justify-between items-center">
                  <label className="text-xs font-semibold text-slate-200">
                    {metaPlatform === 'youtube' ? 'Video Description' : 'Caption & Hashtags'}
                  </label>
                  <span className="text-[11px] font-mono text-slate-500">{metaDescription.length} characters</span>
                </div>
                <textarea
                  rows={4}
                  value={metaDescription}
                  onChange={(e) => setMetaDescription(e.target.value)}
                  className="w-full px-4 py-3 rounded-xl bg-[#181a24] border border-white/10 text-white text-sm focus:outline-none focus:border-violet-500 transition resize-none leading-relaxed"
                />
              </div>

              {/* Platform-Specific Options */}
              {metaPlatform === 'youtube' && (
                <div className="grid grid-cols-2 gap-4">
                  <div className="p-4 rounded-xl bg-[#12141c] border border-white/5 space-y-2">
                    <label className="text-xs font-semibold text-slate-300 block">YouTube Keyword Tags (Comma Separated)</label>
                    <input
                      type="text"
                      value={metaYoutubeTags}
                      onChange={(e) => setMetaYoutubeTags(e.target.value)}
                      className="w-full px-3 py-2 rounded-lg bg-[#181a24] border border-white/10 text-xs text-slate-200 focus:outline-none focus:border-violet-500"
                    />
                  </div>

                  <div className="p-4 rounded-xl bg-[#12141c] border border-white/5 space-y-2">
                    <label className="text-xs font-semibold text-slate-300 block">Visibility Setting</label>
                    <select
                      value={metaPrivacy}
                      onChange={(e) => setMetaPrivacy(e.target.value)}
                      className="w-full px-3 py-2 rounded-lg bg-[#181a24] border border-white/10 text-xs text-slate-200 focus:outline-none"
                    >
                      <option value="public">Public</option>
                      <option value="unlisted">Unlisted</option>
                      <option value="private">Private</option>
                    </select>
                  </div>
                </div>
              )}

              {/* Save & Schedule Bar */}
              <div className="flex justify-end gap-3 pt-4">
                <button
                  onClick={handleSaveClipEdits}
                  className="px-5 py-2.5 rounded-xl bg-white/5 hover:bg-white/10 text-slate-200 text-xs font-semibold border border-white/10 transition"
                >
                  Save Draft
                </button>
                <button
                  onClick={async () => {
                    await handleSaveClipEdits();
                    if (selectedClip) {
                      await fetch(`${API_URL}/api/v1/clips/${selectedClip.id}/publish`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                          platform: metaPlatform === 'youtube' ? 'youtube_shorts' : 'instagram_reels',
                          title: metaTitle,
                          description: metaDescription,
                        }),
                      });
                      setSaveSuccessNotice('Queued for social publishing!');
                      setTimeout(() => setSaveSuccessNotice(null), 3000);
                    }
                  }}
                  className="px-6 py-2.5 rounded-xl bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white text-xs font-semibold shadow-lg shadow-violet-500/20 transition flex items-center gap-2"
                >
                  <Send className="h-4 w-4" /> Queue for {metaPlatform === 'youtube' ? 'YouTube Shorts' : 'Reels'}
                </button>
              </div>
            </div>
          )}

          {/* ── TAB 5: JOB MONITOR & WORKER ───────────────────────── */}
          {activeTab === 'queue' && (
            <div className="max-w-5xl mx-auto space-y-6">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-base font-semibold text-white">Durable Background Task Monitor</h2>
                  <p className="text-xs text-slate-400 mt-0.5">SQLite-backed crash-resilient task execution queue</p>
                </div>
                <button onClick={fetchData} className="text-xs text-slate-400 hover:text-white flex items-center gap-1.5 transition">
                  <RefreshCw className="h-3.5 w-3.5" /> Refresh Jobs
                </button>
              </div>

              <section className="space-y-3 rounded-xl border border-white/5 bg-[#12141c] p-4">
                <h3 className="text-sm font-semibold">Creator monitoring</h3>
                <p className="text-xs text-slate-400">Monitor authorized creator URLs for replay or VOD import. No live capture.</p>
                <form className="flex flex-wrap gap-2" onSubmit={async event => {
                  event.preventDefault();
                  try {
                    const response = await fetch(`${API_URL}/api/v1/monitors`, {
                      method: 'POST', headers: { 'Content-Type': 'application/json' },
                      body: JSON.stringify({ url: creatorUrl }),
                    });
                    if (!response.ok) throw new Error('Could not add monitor. Check the creator URL.');
                    setCreatorUrl('');
                    setMonitorMessage('Monitor saved.');
                    await fetchData();
                  } catch (error) { setMonitorMessage(String(error)); }
                }}>
                  <input aria-label="Creator URL" type="url" required value={creatorUrl} onChange={event => setCreatorUrl(event.target.value)} className="flex-1 rounded bg-slate-900 p-2 text-sm" placeholder="YouTube channel or Kick creator URL" />
                  <button className="rounded bg-violet-600 px-4 text-sm">Add monitor</button>
                </form>
                <p role="status" className="text-xs text-slate-300">{monitorMessage}</p>
                {monitors.map(monitor => (
                  <div key={monitor.id} className="flex flex-wrap items-center justify-between gap-2 border-t border-white/5 pt-2 text-xs">
                    <div className="space-y-1 break-all">
                      <p>{monitor.url}</p>
                      <p className="text-slate-400">{monitor.paused ? 'Paused' : monitor.next_run_at ? `Next poll: ${new Date(monitor.next_run_at).toLocaleString()}` : 'Waiting to schedule'}</p>
                      <p className="text-slate-400">{monitor.last_poll ? `${new Date(monitor.last_poll.at).toLocaleString()} · ${monitor.last_poll.error ?? `${monitor.last_poll.queued ?? 0} newly queued`}` : 'No poll result in this backend session'}</p>
                    </div>
                    <button className="rounded border border-white/10 px-3 py-1" onClick={async () => {
                      try {
                        const response = await fetch(`${API_URL}/api/v1/monitors/${monitor.id}`, {
                          method: 'PATCH', headers: { 'Content-Type': 'application/json' },
                          body: JSON.stringify({ paused: !monitor.paused }),
                        });
                        if (!response.ok) throw new Error('Could not update monitor.');
                        setMonitorMessage(monitor.paused ? 'Monitor resumed.' : 'Monitor paused.');
                        await fetchData();
                      } catch (error) { setMonitorMessage(String(error)); }
                    }}>{monitor.paused ? 'Resume' : 'Pause'}</button>
                  </div>
                ))}
              </section>

              {jobs.length === 0 ? (
                <div className="p-12 text-center rounded-2xl bg-[#12141c] border border-white/5 text-slate-400 text-xs">
                  No active or completed jobs recorded yet.
                </div>
              ) : (
                <div className="space-y-3">
                  {jobs.map((job) => (
                    <div key={job.id} className="p-4 rounded-xl bg-[#12141c] border border-white/5 flex items-center justify-between">
                      <div className="space-y-1 w-1/3">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-semibold text-white uppercase">{job.task_type.replace('_', ' ')}</span>
                          <span
                            className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${
                              job.status === 'completed'
                                ? 'bg-emerald-500/10 text-emerald-300 border border-emerald-500/20'
                                : job.status === 'running' || job.status === 'claimed'
                                ? 'bg-violet-500/10 text-violet-300 border border-violet-500/20 animate-pulse'
                                : job.status === 'failed'
                                ? 'bg-rose-500/10 text-rose-300 border border-rose-500/20'
                                : 'bg-slate-500/10 text-slate-300'
                            }`}
                          >
                            {job.status}
                          </span>
                        </div>
                        <span className="block break-words text-[11px] text-slate-400">{job.progress_message || 'In queue'}</span>
                        {job.status === 'failed' && job.error_message && <p className="break-words text-xs text-rose-300">{job.error_message}</p>}
                        {(['queued', 'running', 'claimed'].includes(job.status) || job.status === 'failed') && <button className="text-xs underline" onClick={async () => {
                          const action = job.status === 'failed' ? 'retry' : 'cancel';
                          try {
                            const response = await fetch(`${API_URL}/api/v1/jobs/${job.id}/${action}`, { method: 'POST' });
                            if (!response.ok) throw new Error(`Could not ${action} job. Refresh its status and try again.`);
                            setSaveSuccessNotice(null);
                            await fetchData();
                          } catch (error) { setSaveSuccessNotice(String(error)); }
                        }}>{job.status === 'failed' ? 'Retry' : 'Cancel'}</button>}
                      </div>

                      {/* Progress Bar */}
                      <div className="w-1/3 px-4">
                        <div className="flex justify-between text-[10px] text-slate-400 mb-1">
                          <span>{job.status === 'running' && job.task_type === 'import_recording' ? 'Downloading...' : 'Progress'}</span>
                          <span>{job.progress}%</span>
                        </div>
                        <div className="h-1.5 w-full bg-white/10 rounded-full overflow-hidden">
                          <div
                            className={`h-full transition-all duration-300 rounded-full ${job.task_type === 'import_recording' ? 'bg-emerald-500' : 'bg-violet-500'}`}
                            style={{ width: `${job.progress}%` }}
                          />
                        </div>
                      </div>

                      <div className="text-right">
                        <span className="text-[10px] font-mono text-slate-500 block">{job.id.slice(0, 8)}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* ── TAB 6: SETTINGS ───────────────────────────────────── */}
          {activeTab === 'settings' && (
            <div className="max-w-4xl mx-auto space-y-6">
              <div>
                <h2 className="text-base font-semibold text-white">Local Configuration & Paths</h2>
                <p className="text-xs text-slate-400 mt-0.5">Windows 11 native endpoints and media storage directories</p>
              </div>

              <div className="p-6 rounded-2xl bg-[#12141c] border border-white/5 space-y-5">
                <div>
                  <label className="text-xs font-semibold text-slate-300 block mb-1">OmniRouter AI Local Gateway</label>
                  <input
                    type="text"
                    disabled
                    value={deps?.omnirouter?.url || 'http://localhost:20128/v1'}
                    className="w-full px-3.5 py-2 rounded-xl bg-[#181a24] border border-white/10 text-xs text-slate-400 font-mono"
                  />
                  <span className="text-[11px] text-slate-500 mt-1 block">Configured via OMNIROUTER_BASE_URL in .env</span>
                </div>

                <div>
                  <label className="text-xs font-semibold text-slate-300 block mb-1">SQLite Database Location</label>
                  <input
                    type="text"
                    disabled
                    value="services/api/data/clipforge.db"
                    className="w-full px-3.5 py-2 rounded-xl bg-[#181a24] border border-white/10 text-xs text-slate-400 font-mono"
                  />
                  <span className="text-[11px] text-slate-500 mt-1 block">Full ACID compliance with WAL mode & foreign keys</span>
                </div>

                <div>
                  <label className="text-xs font-semibold text-slate-300 block mb-1">Media Storage Root</label>
                  <input
                    type="text"
                    disabled
                    value="storage/ (uploads/, clips/, proxies/, thumbnails/)"
                    className="w-full px-3.5 py-2 rounded-xl bg-[#181a24] border border-white/10 text-xs text-slate-400 font-mono"
                  />
                </div>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
