/**
 * frontend/src/components/IngestModal.tsx
 * Offline Satellite Imagery Ingestion and Catalog Management Modal.
 *
 * Implements Sections 11, 16, 25:
 * - Drag & Drop GeoTIFF / COG raster file upload
 * - Sensor selection (Sentinel-2, Landsat, High-Res Optical)
 * - Acquisition date selector
 * - Live pipeline progress (Upload -> Validate -> Cloud Mask -> Tiling -> Embeddings -> FAISS Indexing)
 * - Zero external API keys needed; 100% offline.
 */

import React, { useState } from "react";
import {
  UploadCloud,
  FileCheck,
  Layers,
  Sparkles,
  Database,
  CheckCircle2,
  X,
  Loader2,
  AlertCircle,
  HardDrive,
} from "lucide-react";
import { uploadRasterFile, triggerIngestionProcess } from "../services/api";

interface IngestModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: (sceneId: string) => void;
}

export function IngestModal({ isOpen, onClose, onSuccess }: IngestModalProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [sensor, setSensor] = useState("Sentinel-2");
  const [acquisitionDate, setAcquisitionDate] = useState(new Date().toISOString().split("T")[0]);
  const [uploading, setUploading] = useState(false);
  const [progressStage, setProgressStage] = useState<string | null>(null);
  const [progressPercent, setProgressPercent] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<any | null>(null);

  if (!isOpen) return null;

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0]);
      setError(null);
    }
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setSelectedFile(e.dataTransfer.files[0]);
      setError(null);
    }
  };

  const handleProcess = async () => {
    if (!selectedFile) {
      setError("Please select or drop a satellite raster file (.tif / .tiff / .cog).");
      return;
    }

    setUploading(true);
    setError(null);
    setProgressPercent(15);
    setProgressStage("Uploading GeoTIFF to local secure archive...");

    try {
      // 1. Upload
      const uploadRes = await uploadRasterFile(selectedFile, sensor, acquisitionDate);
      setProgressPercent(40);
      setProgressStage("Preprocessing raster, calculating NDVI & SCL cloud mask...");

      // 2. Process
      setTimeout(() => {
        setProgressPercent(70);
        setProgressStage("Generating 512x512 tiles & Vision-Language embeddings...");
      }, 600);

      const processRes = await triggerIngestionProcess(
        uploadRes.file_path,
        sensor,
        acquisitionDate
      );

      setProgressPercent(100);
      setProgressStage("Complete! Catalog updated and FAISS vector index synced.");
      setResult(processRes);
      if (onSuccess) onSuccess(processRes.scene_id);
    } catch (err: any) {
      setError(err.message || "Ingestion pipeline encountered an error.");
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md p-4 animate-fadeIn">
      <div className="w-full max-w-xl rounded-2xl bg-[#0b0f22] border border-indigo-950/80 shadow-[0_0_50px_rgba(99,102,241,0.25)] flex flex-col overflow-hidden text-slate-100 font-sans">
        {/* Header */}
        <div className="px-6 py-4 border-b border-indigo-950/60 bg-[#0e142c] flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-indigo-500/20 border border-indigo-500/40 flex items-center justify-center text-indigo-400 shadow-[0_0_10px_rgba(99,102,241,0.3)]">
              <UploadCloud className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-white font-mono tracking-wide">
                Ingest Satellite Imagery
              </h3>
              <p className="text-[11px] text-slate-400">
                Offline GeoTIFF / COG Ingestion, Tiling & Vector Indexing Pipeline
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-7 h-7 rounded-lg bg-slate-900 border border-slate-800 text-slate-400 hover:text-white flex items-center justify-center transition"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Body */}
        <div className="p-6 flex flex-col gap-4 overflow-y-auto max-h-[75vh]">
          {/* Dropzone */}
          <div
            onDragOver={(e) => e.preventDefault()}
            onDrop={handleDrop}
            className={`border-2 border-dashed rounded-xl p-6 flex flex-col items-center justify-center text-center cursor-pointer transition ${
              selectedFile
                ? "border-emerald-500/60 bg-emerald-950/10"
                : "border-indigo-900/60 bg-slate-950/50 hover:border-indigo-500/50 hover:bg-indigo-950/20"
            }`}
            onClick={() => document.getElementById("file-input")?.click()}
          >
            <input
              id="file-input"
              type="file"
              accept=".tif,.tiff,.cog,.png,.jpg"
              onChange={handleFileChange}
              className="hidden"
            />
            {selectedFile ? (
              <div className="flex flex-col items-center gap-2">
                <FileCheck className="w-10 h-10 text-emerald-400" />
                <span className="text-xs font-mono font-bold text-emerald-300">
                  {selectedFile.name}
                </span>
                <span className="text-[10px] text-slate-400 font-mono">
                  {(selectedFile.size / (1024 * 1024)).toFixed(2)} MB · Ready to Process
                </span>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-2">
                <HardDrive className="w-9 h-9 text-indigo-400/80" />
                <span className="text-xs font-semibold text-slate-200">
                  Drag and drop satellite GeoTIFF or browse
                </span>
                <span className="text-[10px] text-slate-400">
                  Supports .tif, .tiff, .cog, multi-spectral Sentinel-2 & Landsat
                </span>
              </div>
            )}
          </div>

          {/* Metadata Controls */}
          <div className="grid grid-cols-2 gap-3 text-xs font-mono">
            <div className="flex flex-col gap-1.5">
              <label className="text-[10px] text-slate-400 uppercase tracking-wider">
                Sensor / Platform
              </label>
              <select
                value={sensor}
                onChange={(e) => setSensor(e.target.value)}
                className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-slate-200 focus:outline-none focus:border-indigo-500"
              >
                <option value="Sentinel-2">Sentinel-2 (MSI L2A)</option>
                <option value="Landsat-8">Landsat-8 / 9 (OLI)</option>
                <option value="High-Res Optical">High-Res Optical (Aerial / Commercial)</option>
                <option value="GeoTIFF Generic">Generic Orthorectified GeoTIFF</option>
              </select>
            </div>

            <div className="flex flex-col gap-1.5">
              <label className="text-[10px] text-slate-400 uppercase tracking-wider">
                Acquisition Date
              </label>
              <input
                type="date"
                value={acquisitionDate}
                onChange={(e) => setAcquisitionDate(e.target.value)}
                className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-800 text-slate-200 focus:outline-none focus:border-indigo-500"
              />
            </div>
          </div>

          {/* Progress bar */}
          {progressStage && (
            <div className="p-3.5 rounded-xl bg-slate-950/80 border border-indigo-950/80 flex flex-col gap-2">
              <div className="flex items-center justify-between text-xs font-mono">
                <span className="text-indigo-300 flex items-center gap-2">
                  {uploading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />}
                  {progressStage}
                </span>
                <span className="font-bold text-white">{progressPercent}%</span>
              </div>
              <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-indigo-500 to-emerald-400 transition-all duration-300 rounded-full"
                  style={{ width: `${progressPercent}%` }}
                />
              </div>
            </div>
          )}

          {error && (
            <div className="p-3 rounded-lg bg-rose-950/60 border border-rose-500/40 text-rose-200 text-xs flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* Success summary */}
          {result && (
            <div className="p-3.5 rounded-xl bg-emerald-950/30 border border-emerald-500/40 text-emerald-200 text-xs flex flex-col gap-2">
              <div className="flex items-center gap-2 font-bold font-mono">
                <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                <span>Scene Successfully Ingested & Indexed</span>
              </div>
              <div className="grid grid-cols-2 gap-2 text-[11px] font-mono text-slate-300">
                <div>Scene ID: {result.scene_id}</div>
                <div>Tiles Indexed: {result.tile_count}</div>
                <div>Cloud Cover: {result.cloud_percentage}%</div>
                <div>Status: ACTIVE IN CATALOG</div>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-3.5 border-t border-indigo-950/60 bg-[#0e142c] flex items-center justify-between">
          <span className="text-[10px] font-mono text-slate-500">
            Offline Mode: Local Storage & Local FAISS Indexing
          </span>
          <div className="flex items-center gap-2">
            <button
              onClick={onClose}
              className="px-4 py-2 rounded-lg bg-slate-900 hover:bg-slate-800 text-slate-300 text-xs font-semibold transition"
            >
              Close
            </button>
            <button
              onClick={handleProcess}
              disabled={!selectedFile || uploading}
              className="px-4 py-2 rounded-lg bg-gradient-to-r from-indigo-600 to-indigo-500 hover:from-indigo-500 hover:to-indigo-400 text-white text-xs font-bold transition shadow-[0_0_15px_rgba(99,102,241,0.4)] disabled:opacity-50 flex items-center gap-2"
            >
              {uploading ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>Processing...</span>
                </>
              ) : (
                <>
                  <Layers className="w-3.5 h-3.5" />
                  <span>Execute Ingestion Pipeline</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
