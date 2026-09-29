/**
 * frontend/src/components/IngestPanel.tsx
 * Satellite imagery ingestion triggers and scene catalog view.
 * Phase 3 implementation.
 */

import { useState, useEffect } from "react";
import { AnimatePresence } from "framer-motion";
import {
  Download,
  AlertTriangle,
  Loader2,
} from "lucide-react";

import { useMapStore } from "../stores/mapStore";
import { useSettingsStore } from "../stores/settingsStore";
import { triggerIngest, fetchScenes } from "../services/api";
import { PipelineStepper } from "./PipelineStepper";
import { SceneRecord } from "../types";

export function IngestPanel() {
  const { aoiList, activeAOI, setActiveAOI } = useMapStore();
  const { operatorUsername, operatorPassword } = useSettingsStore();

  const [selectedAOIId, setSelectedAOIId] = useState<string>(activeAOI?.id || "");
  const [startDate, setStartDate] = useState("2024-01-01");
  const [endDate, setEndDate] = useState("2024-02-01");
  const [maxCloud, setMaxCloud] = useState(20);
  const maxScenes = 3;

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [scenes, setScenes] = useState<SceneRecord[]>([]);

  const creds = { username: operatorUsername || "admin", password: operatorPassword || "" };

  // Sync selected AOI with active AOI in store
  useEffect(() => {
    if (activeAOI && activeAOI.id !== selectedAOIId) {
      setSelectedAOIId(activeAOI.id);
    }
  }, [activeAOI]);

  // Load scenes on mount
  const refreshScenes = () => {
    fetchScenes(creds)
      .then((res) => {
        if (res && res.scenes) {
          setScenes(res.scenes);
        }
      })
      .catch(() => {});
  };

  useEffect(() => {
    refreshScenes();
  }, []);

  const handleStartIngest = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const aoiId = selectedAOIId || activeAOI?.id;
    if (!aoiId) {
      setError("Please select or draw an AOI first.");
      return;
    }

    setSubmitting(true);
    try {
      const res = await triggerIngest(
        {
          aoi_id: aoiId,
          start_date: new Date(startDate).toISOString(),
          end_date: new Date(endDate).toISOString(),
          max_cloud_cover: maxCloud,
          max_scenes: maxScenes,
        },
        creds
      );
      setActiveJobId(res.job_id);
    } catch (err: any) {
      setError(err.message || "Failed to trigger ingestion.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex flex-col gap-3 h-full overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-xs font-semibold text-slate-300 uppercase tracking-wider">
          <Download className="w-4 h-4 text-emerald-400" />
          <span>Ingest Imagery</span>
        </div>
      </div>

      {/* Active Pipeline Stepper */}
      <AnimatePresence>
        {activeJobId && (
          <PipelineStepper
            jobId={activeJobId}
            onComplete={() => {
              refreshScenes();
            }}
            onDismiss={() => setActiveJobId(null)}
          />
        )}
      </AnimatePresence>

      {/* Ingestion Form */}
      <form onSubmit={handleStartIngest} className="flex flex-col gap-2.5 bg-slate-900/40 p-3 rounded-lg border border-slate-800">
        <div>
          <label className="text-[11px] text-slate-400 block mb-1">Target AOI</label>
          <select
            value={selectedAOIId}
            onChange={(e) => {
              setSelectedAOIId(e.target.value);
              const found = aoiList.find((a) => a.id === e.target.value);
              if (found) setActiveAOI(found);
            }}
            className="w-full bg-slate-950/80 border border-slate-700/60 rounded px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-emerald-500"
          >
            <option value="">-- Choose an AOI --</option>
            {aoiList.map((aoi) => (
              <option key={aoi.id} value={aoi.id}>
                {aoi.name} ({aoi.area_km2.toFixed(1)} km²)
              </option>
            ))}
          </select>
        </div>

        <div className="grid grid-cols-2 gap-2">
          <div>
            <label className="text-[10px] text-slate-400 block mb-1">Start Date</label>
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="w-full bg-slate-950/80 border border-slate-700/60 rounded px-2 py-1 text-xs text-slate-200 focus:outline-none focus:border-emerald-500"
            />
          </div>
          <div>
            <label className="text-[10px] text-slate-400 block mb-1">End Date</label>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="w-full bg-slate-950/80 border border-slate-700/60 rounded px-2 py-1 text-xs text-slate-200 focus:outline-none focus:border-emerald-500"
            />
          </div>
        </div>

        <div className="flex items-center justify-between text-xs text-slate-400 pt-1">
          <span>Max Cloud Cover: {maxCloud}%</span>
          <input
            type="range"
            min="0"
            max="60"
            value={maxCloud}
            onChange={(e) => setMaxCloud(Number(e.target.value))}
            className="w-28 accent-emerald-500 cursor-pointer"
          />
        </div>

        {error && (
          <div className="text-[11px] text-rose-400 bg-rose-950/30 p-2 rounded border border-rose-900/50 flex gap-1.5 items-center">
            <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <button
          type="submit"
          disabled={submitting}
          className="mt-1 w-full bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white font-medium py-1.5 rounded-lg text-xs flex items-center justify-center gap-1.5 transition shadow"
        >
          {submitting ? (
            <>
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
              <span>Queueing Job...</span>
            </>
          ) : (
            <>
              <Download className="w-3.5 h-3.5" />
              <span>Trigger Ingest</span>
            </>
          )}
        </button>
      </form>

      {/* Ingested Scenes Catalog */}
      <div className="flex-1 overflow-y-auto flex flex-col gap-2 mt-1">
        <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider flex items-center justify-between">
          <span>Ingested Scenes ({scenes.length})</span>
          <button
            onClick={refreshScenes}
            className="text-[10px] text-slate-500 hover:text-slate-300 transition"
          >
            Refresh
          </button>
        </div>

        {scenes.length === 0 ? (
          <p className="text-[11px] text-slate-500 text-center py-4">
            No scenes ingested yet.
          </p>
        ) : (
          scenes.map((scene) => (
            <div
              key={scene.id}
              className="bg-slate-900/40 border border-slate-700/40 p-2.5 rounded-lg text-[11px] text-slate-300"
            >
              <div className="font-medium truncate text-emerald-300 mb-1">
                {scene.product_id}
              </div>
              <div className="flex items-center justify-between text-[10px] text-slate-400">
                <span>{new Date(scene.acquisition_at).toLocaleDateString()}</span>
                <span>Cloud: {scene.cloud_coverage_percent.toFixed(1)}%</span>
                <span>{scene.tile_count || 4} tiles</span>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
