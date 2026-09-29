/**
 * frontend/src/components/AOIPanel.tsx
 * Sidebar panel for AOI management.
 *
 * Features:
 * - Draw mode toggle (rectangle / polygon)
 * - Keyboard GeoJSON AOI entry (text input)
 * - AOI list with area, vertex count, created timestamp
 * - Active AOI highlight
 * - Validation errors shown inline with structured error message
 * - Respects reduce-motion settings
 */

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Pentagon,
  MapPin,
  AlertTriangle,
  CheckCircle2,
  Edit3,
  Loader2,
} from "lucide-react";

import { useMapStore } from "../stores/mapStore";
import { useSettingsStore } from "../stores/settingsStore";
import { useReducedMotion } from "../hooks/useReducedMotion";
import { createAOI } from "../services/api";
import { fadeIn } from "../motion/tokens";
import { AOIRecord } from "../types";

interface AOIPanelProps {
  onAOICreated?: (aoi: AOIRecord) => void;
}

export function AOIPanel({ onAOICreated }: AOIPanelProps) {
  const shouldReduceMotion = useReducedMotion();
  const { drawMode, setDrawMode, aoiList, activeAOI, setActiveAOI, clearDrawing } = useMapStore();
  const { reduceAnimations, operatorUsername, operatorPassword } = useSettingsStore();

  const [nameInput, setNameInput] = useState("AOI " + new Date().toLocaleDateString());
  const [geojsonInput, setGeojsonInput] = useState("");
  const [showGeoInput, setShowGeoInput] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const creds = { username: operatorUsername || "admin", password: operatorPassword || "" };

  const handleDrawMode = (mode: "rectangle" | "polygon") => {
    setError(null);
    if (drawMode === mode) {
      clearDrawing();
    } else {
      setDrawMode(mode);
    }
  };

  const handleSaveGeoJSON = async () => {
    setError(null);
    let geometry: GeoJSON.Polygon;
    try {
      const parsed = JSON.parse(geojsonInput);
      // Accept either a raw geometry or a Feature
      if (parsed.type === "Feature") {
        geometry = parsed.geometry;
      } else {
        geometry = parsed;
      }
    } catch {
      setError("Invalid JSON. Paste a valid GeoJSON Polygon or Feature.");
      return;
    }

    setSaving(true);
    try {
      const aoi = await createAOI(
        { name: nameInput.trim() || "Unnamed AOI", geometry },
        creds
      );
      useMapStore.getState().addAOI(aoi);
      setGeojsonInput("");
      setShowGeoInput(false);
      onAOICreated?.(aoi);
    } catch (e: any) {
      setError(e.message || "Failed to save AOI.");
    } finally {
      setSaving(false);
    }
  };

  const noAnimate = shouldReduceMotion || reduceAnimations;

  return (
    <div className="flex flex-col gap-3 h-full overflow-hidden">
      {/* Section header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-xs font-semibold text-slate-300 uppercase tracking-wider">
          <MapPin className="w-4 h-4 text-indigo-400" />
          <span>Area of Interest</span>
        </div>
        <span className="text-[10px] font-mono text-slate-500">{aoiList.length} saved</span>
      </div>

      {/* AOI name input */}
      <input
        id="aoi-name-input"
        type="text"
        value={nameInput}
        onChange={(e) => setNameInput(e.target.value)}
        placeholder="AOI name..."
        className="w-full bg-slate-900/80 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition"
        aria-label="AOI name"
      />

      {/* Draw controls */}
      <div className="grid grid-cols-2 gap-2">
        <button
          id="draw-polygon-btn"
          onClick={() => handleDrawMode("polygon")}
          className={`flex items-center justify-center gap-1.5 py-2 px-3 rounded-lg border text-xs font-medium transition ${
            drawMode === "polygon"
              ? "bg-indigo-500/20 border-indigo-500/60 text-indigo-300"
              : "bg-slate-900/40 border-slate-700/60 text-slate-400 hover:border-slate-600 hover:text-slate-300"
          }`}
          aria-pressed={drawMode === "polygon"}
          aria-label="Draw polygon AOI on map"
        >
          <Pentagon className="w-3.5 h-3.5" />
          <span>Polygon</span>
        </button>

        <button
          id="enter-geojson-btn"
          onClick={() => setShowGeoInput((v) => !v)}
          className={`flex items-center justify-center gap-1.5 py-2 px-3 rounded-lg border text-xs font-medium transition ${
            showGeoInput
              ? "bg-sky-500/20 border-sky-500/60 text-sky-300"
              : "bg-slate-900/40 border-slate-700/60 text-slate-400 hover:border-slate-600 hover:text-slate-300"
          }`}
          aria-pressed={showGeoInput}
          aria-label="Enter AOI as GeoJSON"
        >
          <Edit3 className="w-3.5 h-3.5" />
          <span>Enter GeoJSON</span>
        </button>
      </div>

      {/* Drawing mode instruction */}
      {drawMode === "polygon" && (
        <div className="px-2.5 py-2 rounded-lg bg-indigo-500/10 border border-indigo-500/20 text-[11px] text-indigo-300 flex items-start gap-2">
          <Pentagon className="w-3.5 h-3.5 shrink-0 mt-0.5 text-indigo-400" />
          <span>Click on the map to add vertices. Double-click to close and save polygon.</span>
        </div>
      )}

      {/* GeoJSON keyboard input */}
      <AnimatePresence>
        {showGeoInput && (
          <motion.div
            variants={noAnimate ? undefined : fadeIn}
            initial="hidden"
            animate="visible"
            exit="exit"
            className="flex flex-col gap-2"
          >
            <textarea
              id="geojson-input"
              value={geojsonInput}
              onChange={(e) => setGeojsonInput(e.target.value)}
              rows={5}
              placeholder={'Paste GeoJSON Polygon or Feature here...\n{"type":"Polygon","coordinates":[[[77.0,28.0],[77.1,28.0],[77.1,28.1],[77.0,28.1],[77.0,28.0]]]}'}
              className="w-full bg-slate-900/90 border border-slate-700 rounded-lg p-2.5 text-[10px] font-mono text-slate-300 placeholder-slate-600 focus:outline-none focus:border-sky-500 transition resize-none"
              aria-label="GeoJSON AOI input"
            />
            <button
              id="save-geojson-btn"
              onClick={handleSaveGeoJSON}
              disabled={saving || !geojsonInput.trim()}
              className="flex items-center justify-center gap-1.5 py-2 rounded-lg bg-sky-500 hover:bg-sky-400 text-slate-950 text-xs font-semibold transition disabled:opacity-50"
            >
              {saving ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <CheckCircle2 className="w-3.5 h-3.5" />
              )}
              {saving ? "Validating & Saving..." : "Validate & Save AOI"}
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Error display */}
      <AnimatePresence>
        {error && (
          <motion.div
            variants={noAnimate ? undefined : fadeIn}
            initial="hidden"
            animate="visible"
            exit="exit"
            className="px-3 py-2 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-300 text-[11px] flex gap-2 items-start"
            role="alert"
          >
            <AlertTriangle className="w-3.5 h-3.5 shrink-0 text-rose-400 mt-0.5" />
            <span>{error}</span>
          </motion.div>
        )}
      </AnimatePresence>

      {/* AOI list */}
      <div className="flex-1 overflow-y-auto flex flex-col gap-2 mt-1">
        <AnimatePresence>
          {aoiList.length === 0 ? (
            <motion.p
              key="empty"
              variants={noAnimate ? undefined : fadeIn}
              initial="hidden"
              animate="visible"
              className="text-[11px] text-slate-500 text-center py-4"
            >
              No AOIs yet. Draw or paste GeoJSON to add one.
            </motion.p>
          ) : (
            aoiList.map((aoi) => (
              <motion.button
                key={aoi.id}
                id={`aoi-item-${aoi.id}`}
                variants={noAnimate ? undefined : fadeIn}
                initial="hidden"
                animate="visible"
                onClick={() => setActiveAOI(activeAOI?.id === aoi.id ? null : aoi)}
                className={`w-full text-left px-3 py-2.5 rounded-lg border transition text-[11px] ${
                  activeAOI?.id === aoi.id
                    ? "bg-indigo-500/10 border-indigo-500/40 text-indigo-200"
                    : "bg-slate-900/40 border-slate-700/40 text-slate-300 hover:border-slate-600"
                }`}
                aria-pressed={activeAOI?.id === aoi.id}
                aria-label={`AOI: ${aoi.name}`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="font-medium truncate">{aoi.name}</div>
                  <div
                    className={`shrink-0 w-2 h-2 rounded-full mt-0.5 ${
                      activeAOI?.id === aoi.id ? "bg-indigo-400" : "bg-slate-600"
                    }`}
                  />
                </div>
                <div className="flex gap-3 mt-1 text-[10px] font-mono text-slate-500">
                  <span>Area: {aoi.area_km2.toFixed(2)} km²</span>
                  <span>{aoi.vertex_count} verts</span>
                </div>
                {aoi.warnings && aoi.warnings.length > 0 && (
                  <div className="flex items-center gap-1 mt-1 text-[10px] text-amber-400">
                    <AlertTriangle className="w-3 h-3" />
                    <span>{aoi.warnings[0]}</span>
                  </div>
                )}
              </motion.button>
            ))
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
