/**
 * frontend/src/components/TimelinePanel.tsx
 * Phase 7 & 8 — Multi-Temporal Timeline & Spectral Index QC Hypotheses.
 */

import { useState } from "react";
import {
  Clock,
  Calendar,
  Cloud,
  AlertCircle,
  TrendingUp,
  Loader2,
} from "lucide-react";
import { fetchTimeline, classifyHypothesis } from "../services/api";
import {
  TimelineResponse,
  HypothesisClassificationResponse,
} from "../types";
import { useSettingsStore } from "../stores/settingsStore";
import { useMapStore } from "../stores/mapStore";

export function TimelinePanel() {
  const { operatorUsername, operatorPassword } = useSettingsStore();
  const { activeAOI, aoiList } = useMapStore();
  const creds = operatorUsername ? { username: operatorUsername, password: operatorPassword } : undefined;

  const [selectedAOIId, setSelectedAOIId] = useState(activeAOI?.id || (aoiList[0]?.id ?? ""));
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [timelineData, setTimelineData] = useState<TimelineResponse | null>(null);

  // Spectral hypothesis inputs
  const [ndviBefore, setNdviBefore] = useState(0.65);
  const [ndviAfter, setNdviAfter] = useState(0.20);
  const [ndbiBefore, setNdbiBefore] = useState(-0.10);
  const [ndbiAfter, setNdbiAfter] = useState(0.35);
  const [ndwiBefore, setNdwiBefore] = useState(-0.25);
  const [ndwiAfter, setNdwiAfter] = useState(-0.30);
  const [areaM2, setAreaM2] = useState(1500);
  const [elongation, setElongation] = useState(1.2);

  const [evaluatingHypothesis, setEvaluatingHypothesis] = useState(false);
  const [hypothesisResult, setHypothesisResult] =
    useState<HypothesisClassificationResponse | null>(null);
  const [activeSection, setActiveSection] = useState<"timeline" | "hypothesis">("timeline");

  const handleFetchTimeline = async () => {
    if (!selectedAOIId) {
      setError("Please select or create an AOI first.");
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const res = await fetchTimeline(selectedAOIId, creds);
      setTimelineData(res);
    } catch (err: any) {
      setError(err.message || "Failed to load timeline");
    } finally {
      setLoading(false);
    }
  };

  const handleClassifyHypothesis = async (e: React.FormEvent) => {
    e.preventDefault();
    setEvaluatingHypothesis(true);
    try {
      const res = await classifyHypothesis(
        {
          ndvi_before: ndviBefore,
          ndvi_after: ndviAfter,
          ndbi_before: ndbiBefore,
          ndbi_after: ndbiAfter,
          ndwi_before: ndwiBefore,
          ndwi_after: ndwiAfter,
          area_m2: areaM2,
          elongation: elongation,
        },
        creds
      );
      setHypothesisResult(res);
    } catch (err: any) {
      alert(`Hypothesis evaluation failed: ${err.message}`);
    } finally {
      setEvaluatingHypothesis(false);
    }
  };

  const applyPreset = (preset: "clearance" | "construction" | "road" | "water") => {
    if (preset === "clearance") {
      setNdviBefore(0.70);
      setNdviAfter(0.15);
      setNdbiBefore(-0.15);
      setNdbiAfter(0.10);
      setNdwiBefore(-0.20);
      setNdwiAfter(-0.25);
      setAreaM2(3500);
      setElongation(1.4);
    } else if (preset === "construction") {
      setNdviBefore(0.40);
      setNdviAfter(0.10);
      setNdbiBefore(-0.05);
      setNdbiAfter(0.45);
      setNdwiBefore(-0.30);
      setNdwiAfter(-0.35);
      setAreaM2(2800);
      setElongation(1.3);
    } else if (preset === "road") {
      setNdviBefore(0.50);
      setNdviAfter(0.15);
      setNdbiBefore(0.00);
      setNdbiAfter(0.38);
      setNdwiBefore(-0.20);
      setNdwiAfter(-0.25);
      setAreaM2(1800);
      setElongation(4.8);
    } else if (preset === "water") {
      setNdviBefore(0.30);
      setNdviAfter(0.05);
      setNdbiBefore(0.10);
      setNdbiAfter(-0.20);
      setNdwiBefore(-0.15);
      setNdwiAfter(0.50);
      setAreaM2(4200);
      setElongation(1.8);
    }
  };

  return (
    <div className="flex flex-col h-full gap-4 text-xs">
      {/* Tab toggle: Timeline vs Spectral Hypothesis */}
      <div className="flex items-center gap-1 border-b border-slate-800 pb-2 shrink-0">
        <button
          onClick={() => setActiveSection("timeline")}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg font-medium transition ${
            activeSection === "timeline"
              ? "bg-sky-500/20 text-sky-400 border border-sky-500/30"
              : "text-slate-400 hover:text-slate-200"
          }`}
        >
          <Clock className="w-3.5 h-3.5" />
          <span>Temporal Trajectory</span>
        </button>
        <button
          onClick={() => setActiveSection("hypothesis")}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg font-medium transition ${
            activeSection === "hypothesis"
              ? "bg-purple-500/20 text-purple-400 border border-purple-500/30"
              : "text-slate-400 hover:text-slate-200"
          }`}
        >
          <TrendingUp className="w-3.5 h-3.5" />
          <span>Spectral QC Classifier</span>
        </button>
      </div>

      {activeSection === "timeline" && (
        <div className="flex-1 flex flex-col gap-3 overflow-hidden">
          {/* AOI selection & load */}
          <div className="flex items-center gap-2 shrink-0">
            <select
              value={selectedAOIId}
              onChange={(e) => setSelectedAOIId(e.target.value)}
              className="flex-1 bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-slate-200 font-mono"
            >
              <option value="">-- Choose AOI --</option>
              {aoiList.map((aoi) => (
                <option key={aoi.id} value={aoi.id}>
                  {aoi.name} ({Math.round(aoi.area_km2)} km²)
                </option>
              ))}
            </select>
            <button
              onClick={handleFetchTimeline}
              disabled={loading || !selectedAOIId}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-sky-500 hover:bg-sky-400 text-slate-950 font-medium transition disabled:opacity-50"
            >
              {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Clock className="w-3.5 h-3.5" />}
              <span>Load</span>
            </button>
          </div>

          {error && (
            <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex gap-2 items-start shrink-0">
              <AlertCircle className="w-4 h-4 shrink-0 text-rose-400 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          {/* Timeline View */}
          <div className="flex-1 overflow-y-auto space-y-3 pr-1">
            {!timelineData && !loading && (
              <div className="h-44 flex flex-col items-center justify-center text-slate-500 text-center px-4">
                <Clock className="w-8 h-8 text-slate-600 mb-2 stroke-[1.5]" />
                <p className="font-medium text-slate-400">No timeline loaded</p>
                <p className="text-[11px] text-slate-600 mt-1">
                  Select an AOI and load its multi-temporal acquisition sequence to track change persistence over time.
                </p>
              </div>
            )}

            {timelineData && (
              <div className="relative pl-6 border-l border-slate-800 space-y-4 ml-2 my-2">
                {timelineData.timeline.map((item, idx) => (
                  <div key={item.scene_id || idx} className="relative">
                    {/* Circle marker */}
                    <div className="absolute -left-[31px] top-1 w-4 h-4 rounded-full bg-slate-900 border-2 border-sky-400 flex items-center justify-center" />

                    <div className="p-3 rounded-xl bg-slate-900/90 border border-slate-800 flex flex-col gap-1.5">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-1.5 font-mono text-slate-200 font-semibold">
                          <Calendar className="w-3.5 h-3.5 text-sky-400" />
                          <span>{item.date}</span>
                        </div>
                        <div className="flex items-center gap-1 text-[10px] text-slate-400 font-mono">
                          <Cloud className="w-3 h-3 text-slate-500" />
                          <span>{item.cloud_cover.toFixed(1)}% cloud</span>
                        </div>
                      </div>

                      <div className="text-[10px] font-mono text-slate-500">
                        Scene: {item.scene_id}
                      </div>

                      {/* Observed Changes on this date */}
                      {item.changes && item.changes.length > 0 ? (
                        <div className="mt-1 space-y-1">
                          {item.changes.map((c, cIdx) => (
                            <div
                              key={c.id || cIdx}
                              className="px-2 py-1 rounded bg-slate-950 border border-slate-800 flex items-center justify-between text-[10px]"
                            >
                              <span className="capitalize text-slate-300 font-medium">
                                {c.change_type.replace(/_/g, " ")}
                              </span>
                              <span
                                className={`font-mono px-1.5 py-0.2 rounded font-bold ${
                                  c.temporal_status === "confirmed"
                                    ? "text-emerald-400 bg-emerald-500/10 border border-emerald-500/20"
                                    : "text-amber-400 bg-amber-500/10 border border-amber-500/20"
                                }`}
                              >
                                {c.temporal_status}
                              </span>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <span className="text-[10px] text-slate-600 italic">No persistent changes</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Spectral Hypothesis Classifier */}
      {activeSection === "hypothesis" && (
        <form onSubmit={handleClassifyHypothesis} className="flex-1 flex flex-col gap-3 overflow-y-auto pr-1">
          {/* Presets */}
          <div>
            <span className="text-[10px] text-slate-500 block uppercase font-mono mb-1.5">
              Rapid Presets:
            </span>
            <div className="grid grid-cols-2 gap-1.5">
              <button
                type="button"
                onClick={() => applyPreset("clearance")}
                className="py-1 px-2 rounded bg-slate-900 hover:bg-slate-800 border border-slate-800 text-[10px] text-slate-300 transition text-left"
              >
                🌲 Forest Clearance (NDVI ↓)
              </button>
              <button
                type="button"
                onClick={() => applyPreset("construction")}
                className="py-1 px-2 rounded bg-slate-900 hover:bg-slate-800 border border-slate-800 text-[10px] text-slate-300 transition text-left"
              >
                🏗️ Construction (NDBI ↑)
              </button>
              <button
                type="button"
                onClick={() => applyPreset("road")}
                className="py-1 px-2 rounded bg-slate-900 hover:bg-slate-800 border border-slate-800 text-[10px] text-slate-300 transition text-left"
              >
                🛣️ Linear Road (Elongated)
              </button>
              <button
                type="button"
                onClick={() => applyPreset("water")}
                className="py-1 px-2 rounded bg-slate-900 hover:bg-slate-800 border border-slate-800 text-[10px] text-slate-300 transition text-left"
              >
                💧 Water Rise (NDWI ↑)
              </button>
            </div>
          </div>

          {/* Metric inputs */}
          <div className="bg-slate-900/60 p-3 rounded-xl border border-slate-800 space-y-2.5">
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-[10px] text-slate-400 block mb-0.5">NDVI Before (T1)</label>
                <input
                  type="number"
                  step="0.05"
                  value={ndviBefore}
                  onChange={(e) => setNdviBefore(parseFloat(e.target.value))}
                  className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-slate-100 font-mono text-[11px]"
                />
              </div>
              <div>
                <label className="text-[10px] text-slate-400 block mb-0.5">NDVI After (T2)</label>
                <input
                  type="number"
                  step="0.05"
                  value={ndviAfter}
                  onChange={(e) => setNdviAfter(parseFloat(e.target.value))}
                  className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-slate-100 font-mono text-[11px]"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-[10px] text-slate-400 block mb-0.5">NDBI Before (T1)</label>
                <input
                  type="number"
                  step="0.05"
                  value={ndbiBefore}
                  onChange={(e) => setNdbiBefore(parseFloat(e.target.value))}
                  className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-slate-100 font-mono text-[11px]"
                />
              </div>
              <div>
                <label className="text-[10px] text-slate-400 block mb-0.5">NDBI After (T2)</label>
                <input
                  type="number"
                  step="0.05"
                  value={ndbiAfter}
                  onChange={(e) => setNdbiAfter(parseFloat(e.target.value))}
                  className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-slate-100 font-mono text-[11px]"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-[10px] text-slate-400 block mb-0.5">NDWI Before (T1)</label>
                <input
                  type="number"
                  step="0.05"
                  value={ndwiBefore}
                  onChange={(e) => setNdwiBefore(parseFloat(e.target.value))}
                  className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-slate-100 font-mono text-[11px]"
                />
              </div>
              <div>
                <label className="text-[10px] text-slate-400 block mb-0.5">NDWI After (T2)</label>
                <input
                  type="number"
                  step="0.05"
                  value={ndwiAfter}
                  onChange={(e) => setNdwiAfter(parseFloat(e.target.value))}
                  className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-slate-100 font-mono text-[11px]"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-[10px] text-slate-400 block mb-0.5">Area (m²)</label>
                <input
                  type="number"
                  value={areaM2}
                  onChange={(e) => setAreaM2(parseFloat(e.target.value))}
                  className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-slate-100 font-mono text-[11px]"
                />
              </div>
              <div>
                <label className="text-[10px] text-slate-400 block mb-0.5">Elongation Ratio</label>
                <input
                  type="number"
                  step="0.1"
                  value={elongation}
                  onChange={(e) => setElongation(parseFloat(e.target.value))}
                  className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-slate-100 font-mono text-[11px]"
                />
              </div>
            </div>
          </div>

          <button
            type="submit"
            disabled={evaluatingHypothesis}
            className="w-full flex items-center justify-center gap-2 py-2 px-3 rounded-lg bg-purple-500 hover:bg-purple-400 text-slate-950 font-medium transition disabled:opacity-50 shrink-0"
          >
            {evaluatingHypothesis ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <TrendingUp className="w-3.5 h-3.5" />
            )}
            <span>Evaluate Hypothesis</span>
          </button>

          {/* Hypothesis Result Card */}
          {hypothesisResult && (
            <div className="p-3.5 rounded-xl bg-purple-500/10 border border-purple-500/30 flex flex-col gap-2 shrink-0">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-purple-300 uppercase tracking-wide text-[11px]">
                  {hypothesisResult.hypothesis_type.replace(/_/g, " ")}
                </span>
                <span className="font-mono text-purple-400 font-bold bg-purple-500/20 px-2 py-0.5 rounded border border-purple-500/40">
                  {Math.round(hypothesisResult.confidence * 100)}% Confidence
                </span>
              </div>
              <p className="text-[11px] text-slate-300 leading-relaxed">
                {hypothesisResult.reasoning}
              </p>
            </div>
          )}
        </form>
      )}
    </div>
  );
}
