import React, { useEffect, useRef } from "react";
import {
  Compass,
  Search,
  ArrowRight,
  ShieldCheck,
  Layers,
  Sparkles,
  Zap,
  Globe2,
  Cpu,
  Database,
  Radio,
} from "lucide-react";

interface MissionViewProps {
  onNavigate: (view: "mission" | "console" | "investigate" | "search") => void;
}

export const MissionView: React.FC<MissionViewProps> = ({ onNavigate }) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  // 3D wireframe rotating globe simulation in canvas with electric indigo / emerald theme
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let animationFrameId: number;
    let rotation = 0;

    const render = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      const cx = canvas.width / 2;
      const cy = canvas.height / 2;
      const radius = 170;

      // Draw outer atmospheric gradient
      const grad = ctx.createRadialGradient(cx, cy, radius * 0.4, cx, cy, radius * 1.35);
      grad.addColorStop(0, "rgba(99, 102, 241, 0.16)");
      grad.addColorStop(0.65, "rgba(168, 85, 247, 0.06)");
      grad.addColorStop(1, "rgba(6, 9, 19, 0)");
      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.arc(cx, cy, radius * 1.35, 0, Math.PI * 2);
      ctx.fill();

      // Draw globe border
      ctx.strokeStyle = "rgba(129, 140, 248, 0.4)";
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.arc(cx, cy, radius, 0, Math.PI * 2);
      ctx.stroke();

      // Draw latitude lines
      for (let lat = -60; lat <= 60; lat += 30) {
        const y = cy + radius * Math.sin((lat * Math.PI) / 180);
        const rLat = radius * Math.cos((lat * Math.PI) / 180);
        ctx.strokeStyle = "rgba(129, 140, 248, 0.15)";
        ctx.beginPath();
        ctx.ellipse(cx, y, rLat, rLat * 0.25, 0, 0, Math.PI * 2);
        ctx.stroke();
      }

      // Draw rotating longitude lines
      for (let lon = 0; lon < 360; lon += 30) {
        const rad = ((lon + rotation) * Math.PI) / 180;
        const xOffset = Math.sin(rad);
        if (Math.cos(rad) > 0) {
          ctx.strokeStyle = "rgba(168, 85, 247, 0.22)";
          ctx.beginPath();
          ctx.ellipse(cx, cy, Math.abs(xOffset) * radius, radius, 0, 0, Math.PI * 2);
          ctx.stroke();
        }
      }

      // Draw orbital satellite path ring (emerald)
      ctx.strokeStyle = "rgba(16, 185, 129, 0.5)";
      ctx.lineWidth = 1.2;
      ctx.setLineDash([4, 6]);
      ctx.beginPath();
      ctx.ellipse(cx, cy, radius * 1.25, radius * 0.55, 0.5, 0, Math.PI * 2);
      ctx.stroke();
      ctx.setLineDash([]);

      // Draw orbiting satellite position
      const satAngle = (rotation * 1.5 * Math.PI) / 180;
      const satX = cx + radius * 1.25 * Math.cos(satAngle);
      const satY = cy + radius * 0.55 * Math.sin(satAngle);
      ctx.fillStyle = "#10b981";
      ctx.shadowColor = "#34d399";
      ctx.shadowBlur = 14;
      ctx.beginPath();
      ctx.arc(satX, satY, 4.5, 0, Math.PI * 2);
      ctx.fill();
      ctx.shadowBlur = 0;

      rotation += 0.45;
      animationFrameId = requestAnimationFrame(render);
    };

    render();

    return () => {
      cancelAnimationFrame(animationFrameId);
    };
  }, []);

  return (
    <div className="flex-1 overflow-y-auto bg-[#060913] text-slate-100 select-text">
      {/* Background glow & subtle cyber cosmic grid */}
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_80%_80%_at_50%_-20%,rgba(99,102,241,0.18),rgba(255,255,255,0))] pointer-events-none" />

      <div className="max-w-7xl mx-auto px-6 py-12 relative z-10 flex flex-col gap-16">
        {/* Hero Section */}
        <section className="flex flex-col lg:flex-row items-center justify-between gap-12 pt-4">
          <div className="flex-1 flex flex-col gap-6 max-w-2xl">
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-indigo-950/70 border border-indigo-500/40 text-indigo-300 text-xs font-mono tracking-wide w-fit">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
              <span>SIH 26227 · AUTONOMOUS EARTH OBSERVATION PLATFORM</span>
            </div>

            <h1 className="text-4xl sm:text-5xl font-extrabold tracking-tight text-white leading-tight">
              TerraPulse AI: Geospatial Intelligence &{" "}
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-indigo-400 via-purple-300 to-emerald-400">
                Terrestrial Change Detection
              </span>{" "}
              at Scale.
            </h1>

            <p className="text-base text-slate-300 leading-relaxed">
              Continuously monitor ground targets, detect infrastructure development, and analyze
              surface modifications using multispectral satellite passes and verified AI change
              intelligence.
            </p>

            {/* CTAs */}
            <div className="flex flex-wrap items-center gap-4 pt-2">
              <button
                id="btn-launch-investigation"
                onClick={() => onNavigate("investigate")}
                className="flex items-center gap-2 px-6 py-3 rounded-lg bg-gradient-to-r from-indigo-600 to-indigo-500 hover:from-indigo-500 hover:to-indigo-400 text-white font-semibold text-sm transition shadow-[0_0_20px_rgba(99,102,241,0.45)] hover:shadow-[0_0_25px_rgba(99,102,241,0.65)]"
              >
                <Search className="w-4 h-4" />
                <span>Launch Investigation</span>
                <ArrowRight className="w-4 h-4 ml-1" />
              </button>

              <button
                id="btn-surveillance-overview"
                onClick={() => onNavigate("console")}
                className="flex items-center gap-2 px-6 py-3 rounded-lg bg-slate-900/90 hover:bg-slate-800 border border-indigo-500/40 text-indigo-200 font-semibold text-sm transition hover:border-indigo-400 shadow-sm"
              >
                <Compass className="w-4 h-4 text-indigo-400" />
                <span>Surveillance Overview</span>
              </button>

              <button
                id="btn-semantic-ai"
                onClick={() => onNavigate("search")}
                className="flex items-center gap-2 px-5 py-3 rounded-lg bg-slate-900/60 hover:bg-slate-800/80 border border-slate-700 text-slate-300 font-medium text-sm transition"
              >
                <Sparkles className="w-4 h-4 text-purple-400" />
                <span>Semantic AI</span>
              </button>
            </div>

            {/* Key Specs */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-6 border-t border-slate-800/80">
              <div className="p-3 rounded-lg bg-slate-900/60 border border-indigo-950/80">
                <span className="text-xl font-bold font-mono text-indigo-400">10m – 0.5m</span>
                <span className="block text-[11px] text-slate-400 uppercase tracking-wider mt-0.5">
                  Multi-Sensor GSD
                </span>
              </div>
              <div className="p-3 rounded-lg bg-slate-900/60 border border-indigo-950/80">
                <span className="text-xl font-bold font-mono text-purple-400">4-Band</span>
                <span className="block text-[11px] text-slate-400 uppercase tracking-wider mt-0.5">
                  RGB + Near-Infrared
                </span>
              </div>
              <div className="p-3 rounded-lg bg-slate-900/60 border border-indigo-950/80">
                <span className="text-xl font-bold font-mono text-sky-400">&lt; 2s</span>
                <span className="block text-[11px] text-slate-400 uppercase tracking-wider mt-0.5">
                  Spectral AI Latency
                </span>
              </div>
              <div className="p-3 rounded-lg bg-slate-900/60 border border-indigo-950/80">
                <span className="text-xl font-bold font-mono text-emerald-400">100%</span>
                <span className="block text-[11px] text-slate-400 uppercase tracking-wider mt-0.5">
                  Empirical Grounding
                </span>
              </div>
            </div>
          </div>

          {/* Right 3D Wireframe Globe */}
          <div className="flex-1 flex justify-center items-center relative w-full max-w-md">
            <canvas
              ref={canvasRef}
              width={420}
              height={420}
              className="w-full max-w-[380px] h-auto drop-shadow-[0_0_35px_rgba(99,102,241,0.3)]"
            />
            <div className="absolute bottom-2 px-3 py-1 rounded-full bg-slate-950/90 border border-indigo-500/30 text-[11px] font-mono text-indigo-300 flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              <span>ORBITAL RECONNAISSANCE · ACTIVE SIMULATION</span>
            </div>
          </div>
        </section>

        {/* Operational Modules */}
        <section className="flex flex-col gap-6">
          <div className="flex flex-col gap-1">
            <span className="text-xs font-mono text-indigo-400 tracking-widest uppercase">
              Operational Modules
            </span>
            <h2 className="text-2xl font-bold text-white tracking-tight">
              Integrated Surveillance Workflows
            </h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {/* Card 1 */}
            <div
              onClick={() => onNavigate("investigate")}
              className="group p-6 rounded-xl bg-slate-900/50 border border-slate-800 hover:border-indigo-500/50 transition cursor-pointer flex flex-col justify-between hover:bg-slate-900/80 relative overflow-hidden"
            >
              <div className="absolute top-0 right-0 w-24 h-24 bg-indigo-500/5 rounded-full blur-2xl group-hover:bg-indigo-500/15 transition" />
              <div className="flex flex-col gap-4">
                <div className="p-3 rounded-lg bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 w-fit">
                  <Search className="w-6 h-6" />
                </div>
                <div>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-indigo-950 border border-indigo-800 text-indigo-300 uppercase">
                    PRIMARY WORKFLOW
                  </span>
                  <h3 className="text-lg font-semibold text-white mt-2 group-hover:text-indigo-300 transition">
                    Target Investigation & Analysis
                  </h3>
                  <p className="text-xs text-slate-400 mt-2 leading-relaxed">
                    Search coordinates or addresses, inspect Sentinel-2 & sub-meter passes, perform
                    split-swipe comparisons, toggle False-Color Infrared (NIR), and review automated
                    AI change reports.
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2 text-xs font-medium text-indigo-400 mt-6 group-hover:translate-x-1 transition">
                <span>Enter Workspace</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </div>
            </div>

            {/* Card 2 */}
            <div
              onClick={() => onNavigate("console")}
              className="group p-6 rounded-xl bg-slate-900/50 border border-slate-800 hover:border-purple-500/50 transition cursor-pointer flex flex-col justify-between hover:bg-slate-900/80 relative overflow-hidden"
            >
              <div className="absolute top-0 right-0 w-24 h-24 bg-purple-500/5 rounded-full blur-2xl group-hover:bg-purple-500/15 transition" />
              <div className="flex flex-col gap-4">
                <div className="p-3 rounded-lg bg-purple-500/10 border border-purple-500/20 text-purple-400 w-fit">
                  <Compass className="w-6 h-6" />
                </div>
                <div>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-purple-950 border border-purple-800 text-purple-300 uppercase">
                    MISSION CONTROL
                  </span>
                  <h3 className="text-lg font-semibold text-white mt-2 group-hover:text-purple-300 transition">
                    Surveillance Overview
                  </h3>
                  <p className="text-xs text-slate-400 mt-2 leading-relaxed">
                    Real-time map console with auto user geolocation detection, direct boundary
                    drawing on the map, sector monitoring telemetry, and live pass scheduling.
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2 text-xs font-medium text-purple-400 mt-6 group-hover:translate-x-1 transition">
                <span>Open Console</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </div>
            </div>

            {/* Card 3 */}
            <div
              onClick={() => onNavigate("search")}
              className="group p-6 rounded-xl bg-slate-900/50 border border-slate-800 hover:border-emerald-500/50 transition cursor-pointer flex flex-col justify-between hover:bg-slate-900/80 relative overflow-hidden"
            >
              <div className="absolute top-0 right-0 w-24 h-24 bg-emerald-500/5 rounded-full blur-2xl group-hover:bg-emerald-500/15 transition" />
              <div className="flex flex-col gap-4">
                <div className="p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 w-fit">
                  <Sparkles className="w-6 h-6" />
                </div>
                <div>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-950 border border-emerald-800 text-emerald-300 uppercase">
                    INTELLIGENCE LAYER
                  </span>
                  <h3 className="text-lg font-semibold text-white mt-2 group-hover:text-emerald-300 transition">
                    Semantic AI Intelligence
                  </h3>
                  <p className="text-xs text-slate-400 mt-2 leading-relaxed">
                    Query satellite archives and detected modifications using plain natural language
                    backed by RemoteCLIP embeddings and high-speed FAISS vector catalog search.
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2 text-xs font-medium text-emerald-400 mt-6 group-hover:translate-x-1 transition">
                <span>Explore Semantic AI</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </div>
            </div>
          </div>
        </section>

        {/* Enterprise Capabilities */}
        <section className="flex flex-col gap-6 pt-4">
          <div className="flex flex-col gap-1">
            <span className="text-xs font-mono text-indigo-400 tracking-widest uppercase">
              Core Architecture
            </span>
            <h2 className="text-2xl font-bold text-white tracking-tight">
              Enterprise Geospatial Capabilities
            </h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            <div className="p-5 rounded-lg bg-slate-900/40 border border-indigo-950/80 flex flex-col gap-2.5">
              <div className="flex items-center gap-2.5 text-indigo-400">
                <Layers className="w-4 h-4" />
                <h4 className="font-semibold text-sm text-slate-200">
                  Multi-Temporal Change Detection
                </h4>
              </div>
              <p className="text-xs text-slate-400 leading-relaxed">
                Bi-temporal and multi-temporal Siamese neural comparison models combined with
                morphological difference extraction to flag ground surface modifications.
              </p>
            </div>

            <div className="p-5 rounded-lg bg-slate-900/40 border border-indigo-950/80 flex flex-col gap-2.5">
              <div className="flex items-center gap-2.5 text-purple-400">
                <Zap className="w-4 h-4" />
                <h4 className="font-semibold text-sm text-slate-200">
                  Multispectral Indexing (NDVI, NDBI)
                </h4>
              </div>
              <p className="text-xs text-slate-400 leading-relaxed">
                Real-time computation of Normalized Difference Vegetation Index (NDVI), Built-up
                Index (NDBI), Water Index (NDWI), and surface Albedo to measure physical shifts.
              </p>
            </div>

            <div className="p-5 rounded-lg bg-slate-900/40 border border-indigo-950/80 flex flex-col gap-2.5">
              <div className="flex items-center gap-2.5 text-emerald-400">
                <ShieldCheck className="w-4 h-4" />
                <h4 className="font-semibold text-sm text-slate-200">
                  False-Alarm Suppression Engine
                </h4>
              </div>
              <p className="text-xs text-slate-400 leading-relaxed">
                Automated cloud, shadow, and haze suppression filters preventing seasonal and
                atmospheric artifacts from triggering erroneous change alerts.
              </p>
            </div>

            <div className="p-5 rounded-lg bg-slate-900/40 border border-indigo-950/80 flex flex-col gap-2.5">
              <div className="flex items-center gap-2.5 text-indigo-300">
                <Cpu className="w-4 h-4" />
                <h4 className="font-semibold text-sm text-slate-200">
                  AI Geospatial Intelligence Agent
                </h4>
              </div>
              <p className="text-xs text-slate-400 leading-relaxed">
                Interactive conversational analyst agent synthesizing structured intelligence
                reports, calculating affected hectares, and answering investigative queries.
              </p>
            </div>

            <div className="p-5 rounded-lg bg-slate-900/40 border border-indigo-950/80 flex flex-col gap-2.5">
              <div className="flex items-center gap-2.5 text-amber-400">
                <Database className="w-4 h-4" />
                <h4 className="font-semibold text-sm text-slate-200">
                  FAISS Vector Natural Query
                </h4>
              </div>
              <p className="text-xs text-slate-400 leading-relaxed">
                Sub-millisecond semantic similarity search across satellite scene catalogs using
                dense embedding indexing and spatial coordinate bounding.
              </p>
            </div>

            <div className="p-5 rounded-lg bg-slate-900/40 border border-indigo-950/80 flex flex-col gap-2.5">
              <div className="flex items-center gap-2.5 text-teal-400">
                <Globe2 className="w-4 h-4" />
                <h4 className="font-semibold text-sm text-slate-200">
                  Sovereign Air-Gapped Deployment
                </h4>
              </div>
              <p className="text-xs text-slate-400 leading-relaxed">
                Fully containerized architecture compatible with on-premise, secure offline data
                centers with PostGIS, GDAL/rasterio, and local PyTorch inference.
              </p>
            </div>
          </div>
        </section>

        {/* Technology Badges */}
        <section className="py-6 border-t border-slate-800/80 flex flex-col gap-3">
          <span className="text-[11px] font-mono text-slate-500 uppercase tracking-widest text-center">
            Geospatial Infrastructure & Production Stack
          </span>
          <div className="flex flex-wrap items-center justify-center gap-3 text-xs font-mono text-slate-400">
            <span className="px-3 py-1 rounded bg-slate-900 border border-indigo-950">
              Copernicus Sentinel-2 API
            </span>
            <span className="px-3 py-1 rounded bg-slate-900 border border-indigo-950">
              Esri Wayback Sub-Meter Archive
            </span>
            <span className="px-3 py-1 rounded bg-slate-900 border border-indigo-950">
              MapLibre GL WGS84 Engine
            </span>
            <span className="px-3 py-1 rounded bg-slate-900 border border-indigo-950">
              FastAPI Async Telemetry
            </span>
            <span className="px-3 py-1 rounded bg-slate-900 border border-indigo-950">
              PostGIS Geospatial Store
            </span>
            <span className="px-3 py-1 rounded bg-slate-900 border border-indigo-950">
              FAISS Vector Retrieval
            </span>
            <span className="px-3 py-1 rounded bg-slate-900 border border-indigo-950">
              GDAL / rasterio Processing
            </span>
            <span className="px-3 py-1 rounded bg-slate-900 border border-indigo-950">
              Three.js Orbit Simulation
            </span>
          </div>
        </section>
      </div>
    </div>
  );
};
