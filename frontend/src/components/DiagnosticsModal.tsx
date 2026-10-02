/**
 * frontend/src/components/DiagnosticsModal.tsx
 * Real-time System Diagnostics Modal (Section 40).
 * Displays genuine hardware, database, PostGIS, FAISS, and model states.
 */

import React, { useState, useEffect } from "react";
import {
  Activity,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Database,
  Cpu,
  HardDrive,
  RefreshCw,
  X,
  Server,
  Layers,
} from "lucide-react";
import { fetchDiagnosticsApi } from "../services/api";

interface DiagnosticsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function DiagnosticsModal({ isOpen, onClose }: DiagnosticsModalProps) {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadDiagnostics = () => {
    setLoading(true);
    setError(null);
    fetchDiagnosticsApi()
      .then((res) => {
        setData(res);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message || "Failed to load diagnostics");
        setLoading(false);
      });
  };

  useEffect(() => {
    if (isOpen) {
      loadDiagnostics();
    }
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md p-4 animate-in fade-in duration-200">
      <div className="w-full max-w-2xl bg-[#0b0f20] border border-indigo-900/60 rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="px-6 py-4 border-b border-indigo-950/80 bg-slate-900/80 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-lg bg-indigo-500/10 border border-indigo-500/30 text-indigo-400">
              <Activity className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-white tracking-wide">
                System Diagnostics & Pipeline Health
              </h2>
              <p className="text-xs text-slate-400 font-mono">
                Live verification of offline services, storage, and models
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={loadDiagnostics}
              disabled={loading}
              className="p-1.5 rounded-lg bg-indigo-950/60 hover:bg-indigo-900/60 text-indigo-300 hover:text-indigo-100 transition border border-indigo-800/40"
              title="Refresh"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
            </button>
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-slate-200 transition"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto space-y-5 text-sm">
          {error && (
            <div className="p-3 rounded-lg bg-rose-950/40 border border-rose-800/60 text-rose-300 text-xs">
              {error}
            </div>
          )}

          {data ? (
            <>
              {/* Overall Status Banner */}
              <div className="flex items-center justify-between p-3.5 rounded-xl bg-slate-900/90 border border-indigo-950">
                <div className="flex items-center gap-2.5">
                  {data.status === "healthy" ? (
                    <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                  ) : (
                    <AlertTriangle className="w-5 h-5 text-amber-400" />
                  )}
                  <div>
                    <span className="font-semibold text-white block">
                      Overall System Status:{" "}
                      <span
                        className={
                          data.status === "healthy" ? "text-emerald-400 uppercase font-mono" : "text-amber-400 uppercase font-mono"
                        }
                      >
                        {data.status}
                      </span>
                    </span>
                    <span className="text-xs text-slate-400">
                      Python {data.backend?.python_version} ({data.backend?.platform})
                    </span>
                  </div>
                </div>
                <span className="text-xs font-mono px-2 py-0.5 rounded bg-indigo-950/80 border border-indigo-700/60 text-indigo-300">
                  OFFLINE-READY
                </span>
              </div>

              {/* Grid of Components */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
                {/* Database & PostGIS */}
                <div className="p-3.5 rounded-xl bg-slate-950/60 border border-slate-800/80 space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 text-slate-200 font-semibold text-xs">
                      <Database className="w-4 h-4 text-indigo-400" />
                      <span>PostgreSQL & PostGIS</span>
                    </div>
                    {data.database?.connected ? (
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 border border-emerald-500/30 text-emerald-400">
                        CONNECTED
                      </span>
                    ) : (
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-500/10 border border-amber-500/30 text-amber-400">
                        DEGRADED
                      </span>
                    )}
                  </div>
                  <div className="text-xs text-slate-400 space-y-1 font-mono">
                    <div className="flex justify-between">
                      <span>PostGIS Extension:</span>
                      <span className={data.database?.postgis_active ? "text-emerald-400" : "text-slate-400"}>
                        {data.database?.postgis_active ? "Active" : "Native Geometries"}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span>Redis Cache:</span>
                      <span className={data.redis?.connected ? "text-emerald-400" : "text-cyan-400"}>
                        {data.redis?.connected ? "Connected" : "Local In-Memory"}
                      </span>
                    </div>
                  </div>
                </div>

                {/* FAISS Vector Search */}
                <div className="p-3.5 rounded-xl bg-slate-950/60 border border-slate-800/80 space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 text-slate-200 font-semibold text-xs">
                      <LayersIcon className="w-4 h-4 text-purple-400" />
                      <span>FAISS Vector Index</span>
                    </div>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-purple-500/10 border border-purple-500/30 text-purple-300">
                      IndexIDMap2
                    </span>
                  </div>
                  <div className="text-xs text-slate-400 space-y-1 font-mono">
                    <div className="flex justify-between">
                      <span>Total Vectors:</span>
                      <span className="text-white font-bold">{data.faiss?.total_vectors ?? 0}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Vector Dimension:</span>
                      <span className="text-slate-300">{data.faiss?.dimension}D</span>
                    </div>
                  </div>
                </div>

                {/* AI Models */}
                <div className="p-3.5 rounded-xl bg-slate-950/60 border border-slate-800/80 space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 text-slate-200 font-semibold text-xs">
                      <Cpu className="w-4 h-4 text-emerald-400" />
                      <span>Embedding Model</span>
                    </div>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 border border-emerald-500/30 text-emerald-300">
                      {data.models?.embedding?.device?.toUpperCase()}
                    </span>
                  </div>
                  <div className="text-xs text-slate-400 space-y-1 font-mono">
                    <div className="flex justify-between">
                      <span>Model:</span>
                      <span className="text-white truncate max-w-[140px]">{data.models?.embedding?.name}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Change Detector:</span>
                      <span className="text-emerald-400">Classical Spectral</span>
                    </div>
                  </div>
                </div>

                {/* Disk Storage */}
                <div className="p-3.5 rounded-xl bg-slate-950/60 border border-slate-800/80 space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 text-slate-200 font-semibold text-xs">
                      <HardDrive className="w-4 h-4 text-amber-400" />
                      <span>Local Storage (data/)</span>
                    </div>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-300">
                      {data.disk?.free_percentage}% Free
                    </span>
                  </div>
                  <div className="text-xs text-slate-400 space-y-1 font-mono">
                    <div className="flex justify-between">
                      <span>Free Space:</span>
                      <span className="text-white font-bold">{data.disk?.free_gb} GB</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Total Capacity:</span>
                      <span className="text-slate-300">{data.disk?.total_gb} GB</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Data Archive Metrics */}
              <div className="p-4 rounded-xl bg-slate-900/60 border border-indigo-950/60 space-y-2">
                <span className="text-xs font-semibold text-slate-300 uppercase tracking-wider block">
                  Database & Archive Metrics
                </span>
                <div className="grid grid-cols-3 gap-2 text-center">
                  <div className="p-2.5 rounded-lg bg-slate-950/80 border border-slate-800/60">
                    <span className="text-base font-bold text-white font-mono block">
                      {data.metrics?.imagery_count ?? 0}
                    </span>
                    <span className="text-[10px] text-slate-400 uppercase tracking-wider">
                      Scenes Ingested
                    </span>
                  </div>
                  <div className="p-2.5 rounded-lg bg-slate-950/80 border border-slate-800/60">
                    <span className="text-base font-bold text-indigo-400 font-mono block">
                      {data.metrics?.tile_count ?? 0}
                    </span>
                    <span className="text-[10px] text-slate-400 uppercase tracking-wider">
                      Processed Tiles
                    </span>
                  </div>
                  <div className="p-2.5 rounded-lg bg-slate-950/80 border border-slate-800/60">
                    <span className="text-base font-bold text-emerald-400 font-mono block">
                      {data.metrics?.embedding_count ?? 0}
                    </span>
                    <span className="text-[10px] text-slate-400 uppercase tracking-wider">
                      Indexed Vectors
                    </span>
                  </div>
                </div>
              </div>
            </>
          ) : (
            <div className="py-12 flex flex-col items-center justify-center text-slate-400 gap-2">
              <RefreshCw className="w-6 h-6 animate-spin text-indigo-400" />
              <span className="text-xs font-mono">Querying system diagnostics...</span>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-indigo-950/80 bg-slate-900/80 flex items-center justify-between">
          <span className="text-[11px] text-slate-500 font-mono">
            GET /api/diagnostics · PostGIS & FAISS Ready
          </span>
          <button
            onClick={onClose}
            className="px-4 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold transition"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
