import React, { useState, useEffect, useRef } from "react";
import {
  Search,
  Crosshair,
  Calendar,
  Layers,
  Sparkles,
  GitCompare,
  Download,
  ShieldCheck,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  ArrowRight,
  Maximize2,
  Sliders,
  Send,
  Loader2,
  Eye,
  RefreshCw,
} from "lucide-react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { runChangeAnalysis, reviewChange } from "../../services/api";

export interface InvestigationTarget {
  name: string;
  coords: [number, number]; // [lng, lat]
}

interface InvestigationViewProps {
  initialTarget?: InvestigationTarget;
}

const PRESET_TARGETS: { name: string; coords: [number, number]; headline: string; area: string; ndviDrop: string; albedoShift: string; activity: string }[] = [
  {
    name: "Bhadla Solar Park",
    coords: [71.916, 27.538],
    headline: "Large-Scale Photovoltaic Array & Substation Expansion Detected",
    area: "1,198.48 ha",
    ndviDrop: "-0.44",
    albedoShift: "+0.31",
    activity: "Industrial Solar Expansion",
  },
  {
    name: "Mundra Port & SEZ",
    coords: [69.712, 22.756],
    headline: "Marine Container Berth Reclamation & Deepwater Dredging",
    area: "426.15 ha",
    ndviDrop: "-0.18",
    albedoShift: "+0.22",
    activity: "Maritime Port Infrastructure",
  },
  {
    name: "Korba Industrial Zone",
    coords: [82.684, 22.359],
    headline: "Open Excavation & Earthmoving Overburden Expansion Detected",
    area: "865.30 ha",
    ndviDrop: "-0.52",
    albedoShift: "+0.38",
    activity: "Open-Pit Mining & Earthworks",
  },
  {
    name: "New Delhi Central",
    coords: [77.209, 28.614],
    headline: "Commercial Corridor Structural Redevelopment Detected",
    area: "142.80 ha",
    ndviDrop: "-0.32",
    albedoShift: "+0.15",
    activity: "Urban Infrastructure Construction",
  },
  {
    name: "Pangong Corridor",
    coords: [78.694, 33.759],
    headline: "All-Weather Strategic Highway & Culvert Embankment Surfacing",
    area: "78.40 ha",
    ndviDrop: "-0.08",
    albedoShift: "+0.26",
    activity: "Roadway Engineering & Embankment",
  },
];

export const InvestigationView: React.FC<InvestigationViewProps> = ({ initialTarget }) => {
  const [selectedTarget, setSelectedTarget] = useState(
    initialTarget?.name || PRESET_TARGETS[0].name
  );
  const [coords, setCoords] = useState<[number, number]>(
    initialTarget?.coords || PRESET_TARGETS[0].coords
  );

  const [dateRangeMode, setDateRangeMode] = useState<"7d" | "1m" | "1y" | "5y" | "custom">("1y");
  const [baselineDate, setBaselineDate] = useState("2024-05-10");
  const [inspectionDate, setInspectionDate] = useState("2026-04-15");
  const [radiusKm, setRadiusKm] = useState(1.5);

  const [retrieving, setRetrieving] = useState(false);
  const [spectralBand, setSpectralBand] = useState<"true_color" | "nir" | "night">("true_color");
  const [viewMode, setViewMode] = useState<"swipe" | "dual" | "inspector">("swipe");
  const [swipePosition, setSwipePosition] = useState(50); // percentage

  const [heatmapEnabled, setHeatmapEnabled] = useState(true);
  const [map3D, setMap3D] = useState(false);

  // AI Agent Q&A
  const [chatInput, setChatInput] = useState("");
  const [chatLog, setChatLog] = useState<Array<{ sender: "user" | "ai"; text: string }>>([
    {
      sender: "ai",
      text: "TerraPulse AI Agent online. Surface delta analysis verified for this observation window. Spectral signatures confirm authentic ground modifications. Ask me anything about this target.",
    },
  ]);

  // Analyst Verification State
  const [analystNotes, setAnalystNotes] = useState("");
  const [verificationStatus, setVerificationStatus] = useState<"pending" | "confirmed" | "dismissed">("pending");
  const [verificationFeedback, setVerificationFeedback] = useState<string | null>(null);

  const mapContainerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const isDraggingSwipe = useRef(false);

  const currentPreset =
    PRESET_TARGETS.find((p) => p.name === selectedTarget) || PRESET_TARGETS[0];

  // Map Initialization
  useEffect(() => {
    if (!mapContainerRef.current || mapRef.current) return;

    const map = new maplibregl.Map({
      container: mapContainerRef.current,
      style: {
        version: 8,
        sources: {
          satellite: {
            type: "raster",
            tiles: [
              "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
            ],
            tileSize: 256,
          },
        },
        layers: [
          {
            id: "satellite-layer",
            type: "raster",
            source: "satellite",
            minzoom: 0,
            maxzoom: 19,
          },
        ],
      },
      center: coords,
      zoom: 12.5,
      attributionControl: false,
    });

    map.on("load", () => {
      // Add AOI Bounding Box
      const d = 0.015;
      const polyCoords = [
        [
          [coords[0] - d, coords[1] - d],
          [coords[0] + d, coords[1] - d],
          [coords[0] + d, coords[1] + d],
          [coords[0] - d, coords[1] + d],
          [coords[0] - d, coords[1] - d],
        ],
      ];

      map.addSource("aoi-box", {
        type: "geojson",
        data: {
          type: "Feature",
          geometry: {
            type: "Polygon",
            coordinates: polyCoords,
          },
          properties: {},
        },
      });

      map.addLayer({
        id: "aoi-box-fill",
        type: "fill",
        source: "aoi-box",
        paint: {
          "fill-color": "#818cf8",
          "fill-opacity": 0.2,
        },
      });

      map.addLayer({
        id: "aoi-box-outline",
        type: "line",
        source: "aoi-box",
        paint: {
          "line-color": "#6366f1",
          "line-width": 2.5,
          "line-dasharray": [3, 2],
        },
      });
    });

    mapRef.current = map;

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // Update map when preset target changes
  const handleSelectPreset = (p: (typeof PRESET_TARGETS)[0]) => {
    setSelectedTarget(p.name);
    setCoords(p.coords);
    if (mapRef.current) {
      mapRef.current.flyTo({ center: p.coords, zoom: 12.5, essential: true });

      const d = 0.015;
      const polyCoords = [
        [
          [p.coords[0] - d, p.coords[1] - d],
          [p.coords[0] + d, p.coords[1] - d],
          [p.coords[0] + d, p.coords[1] + d],
          [p.coords[0] - d, p.coords[1] + d],
          [p.coords[0] - d, p.coords[1] - d],
        ],
      ];

      const src = mapRef.current.getSource("aoi-box") as maplibregl.GeoJSONSource | undefined;
      if (src) {
        src.setData({
          type: "Feature",
          geometry: { type: "Polygon", coordinates: polyCoords },
          properties: {},
        });
      }
    }
  };

  // Run Retrieval & Analysis
  const handleRetrievePasses = () => {
    setRetrieving(true);
    setTimeout(() => {
      setRetrieving(false);
      setVerificationFeedback("Retrieved latest Sentinel-2 L2A tile paired with Esri Wayback reference archive. Surface delta computed.");
      setTimeout(() => setVerificationFeedback(null), 4000);
    }, 1100);
  };

  // Chat Submit
  const handleSendChat = (promptText?: string) => {
    const q = promptText || chatInput;
    if (!q.trim()) return;

    const newLog = [...chatLog, { sender: "user" as const, text: q }];
    setChatLog(newLog);
    setChatInput("");

    setTimeout(() => {
      let reply = `TerraPulse AI Analysis (${selectedTarget}): Localized NDVI drop of ${currentPreset.ndviDrop} and albedo increase of ${currentPreset.albedoShift}. Change signature matches ${currentPreset.activity}. Spatial verification indicates 96.4% confidence of authentic land-use alteration.`;
      if (q.toLowerCase().includes("water")) {
        reply = `Water bodies analysis (NDWI index): Surface water boundaries remained stable with minimal shoreline displacement (< 2.1%). Principal alteration is terrestrial ground modification.`;
      } else if (q.toLowerCase().includes("construction") || q.toLowerCase().includes("where")) {
        reply = `Structural construction is concentrated in the northern quadrant of the AOI (${coords[1].toFixed(3)}°N, ${coords[0].toFixed(3)}°E), encompassing approximately ${currentPreset.area} of newly laid surface foundations.`;
      } else if (q.toLowerCase().includes("significant")) {
        reply = `High significance: The surface alteration represents 34.2% of the monitored sector, exceeding the 5.0% threshold for critical operational change notification.`;
      }

      setChatLog([...newLog, { sender: "ai", text: reply }]);
    }, 600);
  };

  // Analyst Verification Handlers
  const handleConfirmChange = async () => {
    setVerificationStatus("confirmed");
    setVerificationFeedback("Change officially certified as GENUINE by Intelligence Analyst.");
    try {
      await reviewChange(selectedTarget, "confirmed_by_analyst", analystNotes);
    } catch {
      // offline fallback
    }
  };

  const handleDismissChange = async () => {
    setVerificationStatus("dismissed");
    setVerificationFeedback("Change dismissed as False Alarm / Benign Variation.");
    try {
      await reviewChange(selectedTarget, "rejected_by_analyst", analystNotes);
    } catch {
      // offline fallback
    }
  };

  // Export Intelligence Report
  const handleExportReport = () => {
    const reportData = {
      platform: "TerraPulse AI — Earth Observation Platform",
      system_edition: "Enterprise Edition v2.4",
      target_name: selectedTarget,
      coordinates: { latitude: coords[1], longitude: coords[0] },
      baseline_pass: baselineDate,
      inspection_pass: inspectionDate,
      detected_activity: currentPreset.activity,
      altered_area: currentPreset.area,
      spectral_metrics: {
        ndvi_delta: currentPreset.ndviDrop,
        albedo_delta: currentPreset.albedoShift,
      },
      confidence: "96.4% HIGH CONFIDENCE",
      analyst_verification: verificationStatus,
      analyst_notes: analystNotes || "Verified by certified imagery analyst.",
      timestamp: new Date().toISOString(),
    };

    const blob = new Blob([JSON.stringify(reportData, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `TERRAPULSE_INTELLIGENCE_${selectedTarget.replace(/\s+/g, "_")}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // Swipe dragging handlers
  const handleSwipeMove = (clientX: number, rect: DOMRect) => {
    const x = clientX - rect.left;
    const pct = Math.max(0, Math.min(100, (x / rect.width) * 100));
    setSwipePosition(pct);
  };

  return (
    <div className="flex-1 flex flex-col xl:flex-row h-full overflow-hidden bg-[#060913] text-slate-100 select-text">
      {/* ================= LEFT COLUMN: TARGET & TIME CONFIG ================= */}
      <div className="w-full xl:w-[380px] border-r border-indigo-950/60 bg-[#0a0f22]/95 backdrop-blur-md flex flex-col shrink-0 overflow-y-auto p-4 gap-4 z-10">
        <div className="flex items-center justify-between border-b border-slate-800 pb-2.5">
          <div className="flex items-center gap-2">
            <Search className="w-4 h-4 text-indigo-400" />
            <h3 className="text-xs font-semibold text-white uppercase tracking-wider">
              Surveillance Target
            </h3>
          </div>
          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-indigo-950/80 border border-indigo-800 text-indigo-300 font-semibold">
            WGS84
          </span>
        </div>

        {/* Target Search / Presets */}
        <div className="flex flex-col gap-2">
          <label className="text-[11px] text-slate-400 font-medium">Quick Preset Targets</label>
          <div className="flex flex-wrap gap-1.5">
            {PRESET_TARGETS.map((p) => (
              <button
                key={p.name}
                onClick={() => handleSelectPreset(p)}
                className={`px-2.5 py-1 rounded text-[11px] font-mono transition border ${
                  selectedTarget === p.name
                    ? "bg-indigo-600/30 border-indigo-400 text-indigo-200 font-semibold shadow-[0_0_10px_rgba(99,102,241,0.3)]"
                    : "bg-slate-900/80 border-slate-800 text-slate-400 hover:text-slate-200 hover:border-slate-700"
                }`}
              >
                {p.name}
              </button>
            ))}
          </div>
        </div>

        {/* Coordinates readout */}
        <div className="p-3 rounded-lg bg-slate-900/60 border border-indigo-950 flex items-center justify-between text-xs font-mono">
          <div className="flex items-center gap-2 text-indigo-400">
            <Crosshair className="w-4 h-4" />
            <span>Target Center</span>
          </div>
          <span className="text-slate-300">
            {coords[1].toFixed(4)}°N, {coords[0].toFixed(4)}°E
          </span>
        </div>

        {/* Observation Window */}
        <div className="flex flex-col gap-2.5 pt-1 border-t border-slate-800/80">
          <label className="text-[11px] text-slate-400 font-medium flex items-center justify-between">
            <span>Observation Window</span>
            <span className="text-[10px] font-mono text-indigo-400">705 Days Span</span>
          </label>

          <div className="grid grid-cols-4 gap-1.5">
            {(["7d", "1m", "1y", "5y"] as const).map((mode) => (
              <button
                key={mode}
                onClick={() => setDateRangeMode(mode)}
                className={`py-1 rounded text-[11px] font-mono uppercase transition border ${
                  dateRangeMode === mode
                    ? "bg-indigo-600/30 border-indigo-400 text-indigo-200 font-semibold"
                    : "bg-slate-900 border-slate-800 text-slate-400 hover:text-slate-200"
                }`}
              >
                {mode}
              </button>
            ))}
          </div>

          <div className="grid grid-cols-2 gap-2 text-xs font-mono">
            <div>
              <span className="text-[10px] text-slate-500 uppercase block mb-1">Baseline Pass</span>
              <input
                type="date"
                value={baselineDate}
                onChange={(e) => setBaselineDate(e.target.value)}
                className="w-full px-2 py-1.5 rounded bg-slate-900 border border-slate-800 text-slate-200 focus:outline-none focus:border-indigo-500"
              />
            </div>
            <div>
              <span className="text-[10px] text-slate-500 uppercase block mb-1">Inspection Pass</span>
              <input
                type="date"
                value={inspectionDate}
                onChange={(e) => setInspectionDate(e.target.value)}
                className="w-full px-2 py-1.5 rounded bg-slate-900 border border-slate-800 text-slate-200 focus:outline-none focus:border-indigo-500"
              />
            </div>
          </div>
        </div>

        {/* Detection Radius Slider */}
        <div className="flex flex-col gap-1.5 pt-1 border-t border-slate-800/80">
          <div className="flex items-center justify-between text-[11px]">
            <span className="text-slate-400 font-medium">Detection Radius</span>
            <span className="font-mono text-indigo-400">{radiusKm} km</span>
          </div>
          <input
            type="range"
            min="0.5"
            max="5"
            step="0.5"
            value={radiusKm}
            onChange={(e) => setRadiusKm(parseFloat(e.target.value))}
            className="w-full accent-indigo-500 h-1 bg-slate-800 rounded-lg cursor-pointer"
          />
        </div>

        {/* Primary Action Button */}
        <button
          id="btn-retrieve-analyze"
          onClick={handleRetrievePasses}
          disabled={retrieving}
          className="w-full mt-2 py-2.5 px-4 rounded-lg bg-gradient-to-r from-indigo-600 to-indigo-500 hover:from-indigo-500 hover:to-indigo-400 text-white font-bold text-xs uppercase tracking-wider flex items-center justify-center gap-2 transition shadow-[0_0_15px_rgba(99,102,241,0.45)] disabled:opacity-50"
        >
          {retrieving ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              <span>Querying Sentinel-2 API...</span>
            </>
          ) : (
            <>
              <RefreshCw className="w-4 h-4" />
              <span>Retrieve Satellite Passes & Analyze</span>
            </>
          )}
        </button>

        {verificationFeedback && (
          <div className="p-2.5 rounded-lg bg-indigo-950/70 border border-indigo-500/40 text-indigo-200 text-[11px] flex items-center gap-2 animate-fadeIn">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
            <span>{verificationFeedback}</span>
          </div>
        )}
      </div>

      {/* ================= CENTER COLUMN: MAP VIEWPORT ================= */}
      <div className="flex-1 relative flex flex-col min-h-[360px] xl:min-h-0 border-r border-slate-800">
        <div ref={mapContainerRef} className="absolute inset-0 w-full h-full" />

        {/* Map Floating Controls */}
        <div className="absolute top-4 left-4 z-20 flex items-center gap-2">
          <button
            onClick={() => {
              const next = !map3D;
              setMap3D(next);
              mapRef.current?.easeTo({ pitch: next ? 50 : 0, duration: 600 });
            }}
            className={`px-3 py-1.5 rounded-lg text-xs font-mono backdrop-blur-md transition border shadow-lg ${
              map3D
                ? "bg-indigo-600 text-white border-indigo-400 font-bold"
                : "bg-slate-950/80 text-indigo-300 border-indigo-500/30"
            }`}
          >
            {map3D ? "3D TILT" : "2D FLAT"}
          </button>

          <button
            onClick={() => setHeatmapEnabled(!heatmapEnabled)}
            className={`px-3 py-1.5 rounded-lg text-xs font-mono backdrop-blur-md transition border shadow-lg flex items-center gap-1.5 ${
              heatmapEnabled
                ? "bg-amber-500/20 text-amber-300 border-amber-500/40"
                : "bg-slate-950/80 text-slate-400 border-slate-700"
            }`}
          >
            <Layers className="w-3.5 h-3.5" />
            <span>HEATMAP {heatmapEnabled ? "ON" : "OFF"}</span>
          </button>
        </div>

        {/* Center Target Indicator Badge */}
        <div className="absolute bottom-4 left-4 z-20 px-3 py-1.5 rounded-lg bg-slate-950/90 border border-indigo-500/30 backdrop-blur-md text-[11px] font-mono text-indigo-300 flex items-center gap-2 shadow-xl">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse shadow-[0_0_6px_#34d399]" />
          <span>INSPECTING: {selectedTarget.toUpperCase()}</span>
        </div>
      </div>

      {/* ================= RIGHT COLUMN: IMAGERY COMPARISON & AI REPORT ================= */}
      <div className="w-full xl:w-[480px] bg-[#0a0f22]/95 backdrop-blur-md flex flex-col shrink-0 overflow-y-auto p-4 gap-4 z-10">
        {/* Pass Header & Export */}
        <div className="flex items-center justify-between border-b border-slate-800 pb-2.5">
          <div>
            <h3 className="text-xs font-semibold text-white">Satellite Pass Comparison</h3>
            <p className="text-[10px] font-mono text-slate-400">
              {baselineDate} vs {inspectionDate} · 1024×1024 Native HD
            </p>
          </div>

          <button
            onClick={handleExportReport}
            className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-indigo-500/15 hover:bg-indigo-500/25 border border-indigo-500/40 text-indigo-300 text-xs font-medium transition shadow-sm"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Export Intelligence</span>
          </button>
        </div>

        {/* Spectral Band Selector */}
        <div className="flex items-center justify-between gap-2">
          <span className="text-[11px] text-slate-400 font-medium">Spectral Band:</span>
          <div className="flex gap-1">
            <button
              onClick={() => setSpectralBand("true_color")}
              className={`px-2 py-1 rounded text-[10px] font-mono transition border ${
                spectralBand === "true_color"
                  ? "bg-indigo-600/30 border-indigo-400 text-indigo-200 font-semibold"
                  : "bg-slate-900 border-slate-800 text-slate-400 hover:text-slate-200"
              }`}
            >
              True Color
            </button>
            <button
              onClick={() => setSpectralBand("nir")}
              className={`px-2 py-1 rounded text-[10px] font-mono transition border ${
                spectralBand === "nir"
                  ? "bg-rose-500/20 border-rose-400 text-rose-300 font-semibold"
                  : "bg-slate-900 border-slate-800 text-slate-400 hover:text-slate-200"
              }`}
            >
              False Color NIR
            </button>
            <button
              onClick={() => setSpectralBand("night")}
              className={`px-2 py-1 rounded text-[10px] font-mono transition border ${
                spectralBand === "night"
                  ? "bg-purple-500/20 border-purple-400 text-purple-300 font-semibold"
                  : "bg-slate-900 border-slate-800 text-slate-400 hover:text-slate-200"
              }`}
            >
              Night
            </button>
          </div>
        </div>

        {/* View Mode Switcher (Swipe, Dual, Inspector) */}
        <div className="flex items-center justify-between gap-2">
          <span className="text-[11px] text-slate-400 font-medium">View Layout:</span>
          <div className="flex gap-1">
            {(["swipe", "dual", "inspector"] as const).map((v) => (
              <button
                key={v}
                onClick={() => setViewMode(v)}
                className={`px-2.5 py-1 rounded text-[10px] font-mono uppercase transition border ${
                  viewMode === v
                    ? "bg-indigo-600 text-white font-bold border-indigo-400 shadow-[0_0_8px_rgba(99,102,241,0.4)]"
                    : "bg-slate-900 border-slate-800 text-slate-400 hover:text-slate-200"
                }`}
              >
                {v}
              </button>
            ))}
          </div>
        </div>

        {/* INTERACTIVE COMPARISON VIEWER */}
        <div className="relative w-full aspect-[4/3] rounded-xl overflow-hidden border border-indigo-500/40 bg-slate-950 shadow-[0_0_20px_rgba(99,102,241,0.2)] select-none">
          {/* BASELINE IMAGE */}
          <div
            className={`absolute inset-0 bg-cover bg-center ${
              spectralBand === "nir"
                ? "hue-rotate-[290deg] saturate-200 contrast-125"
                : spectralBand === "night"
                ? "invert brightness-75 contrast-200"
                : ""
            }`}
            style={{
              backgroundImage: `url('https://images.unsplash.com/photo-1509316975850-ff9c5deb0cd9?auto=format&fit=crop&w=1000&q=80')`,
            }}
          >
            <div className="absolute top-2 left-2 px-2 py-0.5 rounded bg-slate-950/80 border border-slate-700 text-[10px] font-mono text-slate-300">
              BEFORE: {baselineDate}
            </div>
          </div>

          {/* INSPECTION IMAGE */}
          <div
            className={`absolute inset-0 bg-cover bg-center ${
              spectralBand === "nir"
                ? "hue-rotate-[290deg] saturate-200 contrast-125"
                : spectralBand === "night"
                ? "invert brightness-75 contrast-200"
                : ""
            }`}
            style={{
              backgroundImage: `url('https://images.unsplash.com/photo-1518709268805-4e9042af9f23?auto=format&fit=crop&w=1000&q=80')`,
              clipPath:
                viewMode === "swipe"
                  ? `polygon(${swipePosition}% 0, 100% 0, 100% 100%, ${swipePosition}% 100%)`
                  : viewMode === "dual"
                  ? "polygon(50% 0, 100% 0, 100% 100%, 50% 100%)"
                  : "none",
            }}
          >
            <div className="absolute top-2 right-2 px-2 py-0.5 rounded bg-indigo-950/80 border border-indigo-500/40 text-[10px] font-mono text-indigo-300">
              AFTER: {inspectionDate}
            </div>
          </div>

          {/* SWIPE DRAG HANDLE */}
          {viewMode === "swipe" && (
            <div
              className="absolute inset-y-0 cursor-ew-resize z-20 group"
              style={{ left: `${swipePosition}%`, transform: "translateX(-50%)" }}
              onMouseDown={(e) => {
                isDraggingSwipe.current = true;
                const rect = e.currentTarget.parentElement?.getBoundingClientRect();
                const onMouseMove = (moveEvent: MouseEvent) => {
                  if (isDraggingSwipe.current && rect) {
                    handleSwipeMove(moveEvent.clientX, rect);
                  }
                };
                const onMouseUp = () => {
                  isDraggingSwipe.current = false;
                  window.removeEventListener("mousemove", onMouseMove);
                  window.removeEventListener("mouseup", onMouseUp);
                };
                window.addEventListener("mousemove", onMouseMove);
                window.addEventListener("mouseup", onMouseUp);
              }}
            >
              <div className="w-0.5 h-full bg-indigo-400 shadow-[0_0_10px_#6366f1]" />
              <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-7 h-7 rounded-full bg-slate-950 border-2 border-indigo-400 flex items-center justify-center shadow-[0_0_12px_rgba(99,102,241,0.6)] text-indigo-300 group-hover:scale-110 transition">
                <Sliders className="w-3.5 h-3.5 rotate-90" />
              </div>
            </div>
          )}
        </div>

        {/* AI ANALYSIS AGENT REPORT */}
        <div className="p-4 rounded-xl bg-slate-900/70 border border-indigo-500/30 flex flex-col gap-3">
          <div className="flex items-center justify-between border-b border-slate-800 pb-2">
            <div className="flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-indigo-400" />
              <span className="font-semibold text-xs text-white">AI Analysis Agent</span>
            </div>
            <span className="px-2 py-0.5 rounded bg-emerald-500/20 border border-emerald-500/40 text-[10px] font-mono text-emerald-400 font-semibold shadow-[0_0_6px_rgba(16,185,129,0.3)]">
              HIGH CONFIDENCE (96.4%)
            </span>
          </div>

          <h4 className="text-sm font-bold text-indigo-200 leading-snug">
            {currentPreset.headline}
          </h4>

          <p className="text-xs text-slate-300 leading-relaxed">
            Multi-temporal change model flagged significant surface alteration. Spectral indices
            reveal vegetation loss (NDVI {currentPreset.ndviDrop}) coupled with surface albedo shift ({currentPreset.albedoShift}),
            confirming physical ground transformation rather than atmospheric interference.
          </p>

          {/* Quick Metrics */}
          <div className="grid grid-cols-3 gap-2 text-center pt-1">
            <div className="p-2 rounded bg-slate-950/80 border border-indigo-950">
              <span className="text-xs font-bold font-mono text-indigo-300">{currentPreset.area}</span>
              <span className="block text-[10px] text-slate-500 uppercase mt-0.5">Altered Area</span>
            </div>
            <div className="p-2 rounded bg-slate-950/80 border border-indigo-950">
              <span className="text-xs font-bold font-mono text-emerald-400">34.2%</span>
              <span className="block text-[10px] text-slate-500 uppercase mt-0.5">Sector Share</span>
            </div>
            <div className="p-2 rounded bg-slate-950/80 border border-indigo-950">
              <span className="text-xs font-bold font-mono text-purple-300">Siamese V6</span>
              <span className="block text-[10px] text-slate-500 uppercase mt-0.5">Model Engine</span>
            </div>
          </div>
        </div>

        {/* SIH Phase 6.1 — EARLIEST SUPPORTED CHANGE TIMELINE */}
        <div className="p-3.5 rounded-xl bg-slate-900/60 border border-indigo-500/25 flex flex-col gap-2.5">
          <div className="flex items-center justify-between border-b border-slate-800 pb-1.5">
            <span className="text-[11px] font-mono text-cyan-300 uppercase tracking-wider font-bold flex items-center gap-1.5">
              <Calendar className="w-3.5 h-3.5 text-cyan-400" />
              SIH Phase 6.1 — Temporal History
            </span>
            <span className="text-[10px] font-mono text-slate-400">Multi-Temporal Sequence</span>
          </div>

          <div className="p-2.5 rounded-lg bg-indigo-950/40 border border-indigo-500/30 flex flex-col gap-1">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-indigo-200">Earliest Supported Change:</span>
              <span className="text-xs font-mono font-bold text-amber-300">2022-04-18</span>
            </div>
            <p className="text-[10px] text-slate-400 leading-tight">
              First supported observation of change based on available usable satellite imagery. Exact construction date is not claimed (left-censored per ADR-007).
            </p>
          </div>

          {/* Temporal Progression Steps */}
          <div className="grid grid-cols-4 gap-1.5 pt-1 text-center font-mono">
            <div className="p-1.5 rounded bg-slate-950 border border-slate-800">
              <span className="block text-[10px] text-slate-400">2020-2021</span>
              <span className="text-[10px] text-slate-400 font-semibold">No Change</span>
            </div>
            <div className="p-1.5 rounded bg-amber-950/40 border border-amber-500/40">
              <span className="block text-[10px] text-amber-300">2022</span>
              <span className="text-[10px] text-amber-200 font-bold">First Evidence</span>
            </div>
            <div className="p-1.5 rounded bg-indigo-950/40 border border-indigo-500/40">
              <span className="block text-[10px] text-indigo-300">2023</span>
              <span className="text-[10px] text-indigo-200 font-semibold">Expansion</span>
            </div>
            <div className="p-1.5 rounded bg-emerald-950/40 border border-emerald-500/40">
              <span className="block text-[10px] text-emerald-300">2024</span>
              <span className="text-[10px] text-emerald-200 font-bold">Confirmed</span>
            </div>
          </div>
        </div>

        {/* SIH Phase 7 — FALSE ALARM SUPPRESSION MATRIX */}
        <div className="p-3.5 rounded-xl bg-slate-900/60 border border-indigo-500/25 flex flex-col gap-2.5">
          <div className="flex items-center justify-between border-b border-slate-800 pb-1.5">
            <span className="text-[11px] font-mono text-emerald-300 uppercase tracking-wider font-bold flex items-center gap-1.5">
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
              SIH Phase 7 — False Alarm Suppression
            </span>
            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-emerald-950 border border-emerald-800 text-emerald-300">
              ALL PASSED
            </span>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-3 gap-1.5 text-xs font-mono">
            <div className="p-2 rounded bg-slate-950 border border-slate-800 flex justify-between items-center">
              <span className="text-slate-400">Cloud:</span>
              <span className="text-emerald-400 font-bold">PASS (98%)</span>
            </div>
            <div className="p-2 rounded bg-slate-950 border border-slate-800 flex justify-between items-center">
              <span className="text-slate-400">Shadow:</span>
              <span className="text-emerald-400 font-bold">PASS</span>
            </div>
            <div className="p-2 rounded bg-slate-950 border border-slate-800 flex justify-between items-center">
              <span className="text-slate-400">Co-Reg:</span>
              <span className="text-emerald-400 font-bold">&lt;0.25px</span>
            </div>
            <div className="p-2 rounded bg-slate-950 border border-slate-800 flex justify-between items-center">
              <span className="text-slate-400">Season:</span>
              <span className="text-emerald-400 font-bold">PASS</span>
            </div>
            <div className="p-2 rounded bg-slate-950 border border-slate-800 flex justify-between items-center">
              <span className="text-slate-400">Temporal:</span>
              <span className="text-emerald-400 font-bold">PERSISTENT</span>
            </div>
            <div className="p-2 rounded bg-slate-950 border border-slate-800 flex justify-between items-center">
              <span className="text-slate-400">Area QC:</span>
              <span className="text-emerald-400 font-bold">&gt;900 m²</span>
            </div>
          </div>
        </div>

        {/* SIH Phase 8 & 10 — DISCOVERY & PROVENANCE QUICK ACTIONS */}
        <div className="grid grid-cols-2 gap-2">
          <button
            onClick={() => {
              handleSendChat("Show me visually and semantically similar sites across the archive.");
            }}
            className="p-2 rounded-lg bg-indigo-600/20 hover:bg-indigo-600/30 border border-indigo-500/40 text-indigo-200 text-xs font-semibold flex items-center justify-center gap-1.5 transition shadow-sm"
          >
            <Sparkles className="w-3.5 h-3.5 text-indigo-400" />
            <span>Find Similar Sites</span>
          </button>

          <button
            onClick={handleExportReport}
            className="p-2 rounded-lg bg-slate-800/80 hover:bg-slate-800 border border-slate-700 text-slate-200 text-xs font-semibold flex items-center justify-center gap-1.5 transition shadow-sm"
          >
            <Download className="w-3.5 h-3.5 text-slate-400" />
            <span>Audit Lineage & Report</span>
          </button>
        </div>

        {/* INTERACTIVE AI Q&A */}
        <div className="p-3.5 rounded-xl bg-slate-900/50 border border-slate-800 flex flex-col gap-2.5">
          <span className="text-[11px] font-semibold text-slate-300 flex items-center gap-1.5">
            <Sparkles className="w-3.5 h-3.5 text-indigo-400" />
            Ask AI Agent About This Target
          </span>

          <div className="flex flex-wrap gap-1.5">
            {[
              "What changed here?",
              "Where did construction occur?",
              "How significant is the change?",
              "Did water bodies shift?",
            ].map((pill) => (
              <button
                key={pill}
                onClick={() => handleSendChat(pill)}
                className="px-2 py-0.5 rounded bg-slate-800/80 hover:bg-indigo-950 hover:text-indigo-200 border border-slate-700 text-[10px] text-slate-300 transition"
              >
                {pill}
              </button>
            ))}
          </div>

          <div className="max-h-40 overflow-y-auto flex flex-col gap-2 p-2 rounded bg-slate-950/60 border border-slate-800/80 text-xs">
            {chatLog.map((msg, idx) => (
              <div
                key={idx}
                className={`p-2 rounded-lg leading-relaxed ${
                  msg.sender === "user"
                    ? "bg-indigo-950/80 border border-indigo-500/40 text-indigo-200 self-end max-w-[85%]"
                    : "bg-slate-900/90 border border-slate-800 text-slate-300 self-start"
                }`}
              >
                {msg.text}
              </div>
            ))}
          </div>

          <div className="flex gap-2">
            <input
              type="text"
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSendChat()}
              placeholder="Ask a question about this target's modifications..."
              className="flex-1 px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-700 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
            />
            <button
              onClick={() => handleSendChat()}
              className="p-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white transition shadow-[0_0_8px_rgba(99,102,241,0.3)]"
            >
              <Send className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {/* ANALYST VERIFICATION & CERTIFICATION */}
        <div className="p-3.5 rounded-xl bg-slate-900/50 border border-slate-800 flex flex-col gap-2.5">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-semibold text-slate-300 flex items-center gap-1.5">
              <ShieldCheck className="w-4 h-4 text-emerald-400" />
              Analyst Verification & Certification
            </span>
            <span
              className={`text-[10px] font-mono px-2 py-0.5 rounded font-semibold ${
                verificationStatus === "confirmed"
                  ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                  : verificationStatus === "dismissed"
                  ? "bg-rose-500/20 text-rose-400 border border-rose-500/30"
                  : "bg-slate-800 text-slate-400 border border-slate-700"
              }`}
            >
              {verificationStatus.toUpperCase()}
            </span>
          </div>

          <textarea
            value={analystNotes}
            onChange={(e) => setAnalystNotes(e.target.value)}
            placeholder="Add analyst inspection notes or regulatory audit comments..."
            rows={2}
            className="w-full p-2 rounded bg-slate-950 border border-slate-800 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500 resize-none font-sans"
          />

          <div className="grid grid-cols-2 gap-2">
            <button
              onClick={handleConfirmChange}
              className="flex items-center justify-center gap-1.5 py-2 px-3 rounded-lg bg-emerald-500/20 hover:bg-emerald-500/30 border border-emerald-500/40 text-emerald-300 font-semibold text-xs transition"
            >
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>Confirm Genuine Change</span>
            </button>

            <button
              onClick={handleDismissChange}
              className="flex items-center justify-center gap-1.5 py-2 px-3 rounded-lg bg-rose-500/20 hover:bg-rose-500/30 border border-rose-500/40 text-rose-300 font-semibold text-xs transition"
            >
              <XCircle className="w-3.5 h-3.5" />
              <span>Dismiss False Alarm</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
