/**
 * frontend/src/components/SearchResultsPanel.tsx
 * Phase 5 — Semantic Retrieval & Visual Tile Search Panel.
 */

import { useState } from "react";
import {
  Search,
  Image as ImageIcon,
  Sparkles,
  Layers,
  Calendar,
  Cloud,
  Loader2,
  AlertCircle,
} from "lucide-react";
import { searchSemantic, searchImage, searchSimilar } from "../services/api";
import { SearchResultItem, SearchResponse } from "../types";
import { useSettingsStore } from "../stores/settingsStore";
import { useMapStore } from "../stores/mapStore";

interface SearchResultsPanelProps {
  initialQuery?: string;
  onSelectForChange?: (tileId: string, role: "before" | "after") => void;
}

export function SearchResultsPanel({ initialQuery = "", onSelectForChange }: SearchResultsPanelProps) {
  const { operatorUsername, operatorPassword } = useSettingsStore();
  const { activeAOI } = useMapStore();
  const creds = operatorUsername ? { username: operatorUsername, password: operatorPassword } : undefined;

  const [query, setQuery] = useState(initialQuery || "deforestation and cleared land");
  const [topK, setTopK] = useState(10);
  const [threshold, setThreshold] = useState(0.2);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<SearchResultItem[]>([]);
  const [activeSearchType, setActiveSearchType] = useState<"text" | "image">("text");
  const [lastSearchedQuery, setLastSearchedQuery] = useState<string>("");

  const handleSemanticSearch = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!query.trim()) return;

    setLoading(true);
    setError(null);
    try {
      const res: SearchResponse = await searchSemantic(
        {
          query: query.trim(),
          top_k: topK,
          threshold: threshold,
          aoi_id: activeAOI?.id,
        },
        creds
      );
      setResults(res.results || []);
      setLastSearchedQuery(query.trim());
    } catch (err: any) {
      setError(err.message || "Failed to execute semantic search");
    } finally {
      setLoading(false);
    }
  };

  const handleImageUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setLoading(true);
    setError(null);
    try {
      const res = await searchImage(file, creds);
      setResults(res.results || []);
      setLastSearchedQuery(`Image query: ${file.name}`);
    } catch (err: any) {
      setError(err.message || "Failed to search by image");
    } finally {
      setLoading(false);
    }
  };

  const handleFindSimilar = async (tileId: string) => {
    setLoading(true);
    setError(null);
    try {
      const res = await searchSimilar(tileId, topK, creds);
      setResults(res.results || []);
      setLastSearchedQuery(`Similar to ${tileId.slice(0, 8)}...`);
    } catch (err: any) {
      setError(err.message || "Failed to find similar tiles");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full gap-4 text-xs">
      {/* Search Header & Type Toggle */}
      <div className="flex items-center justify-between border-b border-slate-800 pb-2 shrink-0">
        <div className="flex items-center gap-2">
          <button
            onClick={() => setActiveSearchType("text")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg font-medium transition ${
              activeSearchType === "text"
                ? "bg-sky-500/20 text-sky-400 border border-sky-500/30"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>Semantic Prompt</span>
          </button>
          <label
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg font-medium cursor-pointer transition ${
              activeSearchType === "image"
                ? "bg-sky-500/20 text-sky-400 border border-sky-500/30"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            <ImageIcon className="w-3.5 h-3.5" />
            <span>Image Query</span>
            <input
              type="file"
              accept="image/png,image/jpeg,image/tiff"
              onChange={handleImageUpload}
              className="hidden"
            />
          </label>
        </div>

        {activeAOI && (
          <span className="text-[10px] font-mono text-indigo-400 bg-indigo-500/10 px-2 py-0.5 rounded border border-indigo-500/20">
            AOI: {activeAOI.name.slice(0, 14)}
          </span>
        )}
      </div>

      {/* Search Form (Text) */}
      {activeSearchType === "text" && (
        <form onSubmit={handleSemanticSearch} className="flex flex-col gap-2 shrink-0">
          <div className="relative">
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="e.g., cleared forest area, industrial warehouses..."
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-sky-500 transition font-sans pr-8"
            />
            <Search className="w-4 h-4 text-slate-500 absolute right-2.5 top-2.5 pointer-events-none" />
          </div>

          {/* Filter tuning: Top-K & Threshold */}
          <div className="grid grid-cols-2 gap-2 bg-slate-900/60 p-2.5 rounded-lg border border-slate-800">
            <div>
              <div className="flex justify-between text-[10px] text-slate-400 mb-1">
                <span>Top Results (K)</span>
                <span className="font-mono text-slate-200">{topK}</span>
              </div>
              <input
                type="range"
                min="1"
                max="50"
                value={topK}
                onChange={(e) => setTopK(Number(e.target.value))}
                className="w-full accent-sky-500 h-1 bg-slate-700 rounded cursor-pointer"
              />
            </div>
            <div>
              <div className="flex justify-between text-[10px] text-slate-400 mb-1">
                <span>Threshold</span>
                <span className="font-mono text-slate-200">{threshold.toFixed(2)}</span>
              </div>
              <input
                type="range"
                min="0"
                max="0.8"
                step="0.05"
                value={threshold}
                onChange={(e) => setThreshold(Number(e.target.value))}
                className="w-full accent-sky-500 h-1 bg-slate-700 rounded cursor-pointer"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full flex items-center justify-center gap-2 py-2 px-3 rounded-lg bg-sky-500 hover:bg-sky-400 text-slate-950 font-medium transition disabled:opacity-50"
          >
            {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Search className="w-3.5 h-3.5" />}
            <span>{loading ? "Searching Embedding Index..." : "Search Imagery"}</span>
          </button>
        </form>
      )}

      {/* Error state */}
      {error && (
        <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex gap-2 items-start shrink-0">
          <AlertCircle className="w-4 h-4 shrink-0 text-rose-400 mt-0.5" />
          <span>{error}</span>
        </div>
      )}

      {/* Results Header */}
      {lastSearchedQuery && !loading && (
        <div className="flex items-center justify-between text-[11px] text-slate-400 border-b border-slate-800/80 pb-1.5 shrink-0">
          <span>{results.length} matches found</span>
          <span className="truncate max-w-[180px] font-mono text-[10px] text-slate-500">
            "{lastSearchedQuery}"
          </span>
        </div>
      )}

      {/* Results List */}
      <div className="flex-1 overflow-y-auto space-y-2.5 pr-1">
        {results.length === 0 && !loading && (
          <div className="h-44 flex flex-col items-center justify-center text-slate-500 text-center px-4">
            <Layers className="w-8 h-8 text-slate-600 mb-2 stroke-[1.5]" />
            <p className="font-medium text-slate-400">No tiles retrieved yet</p>
            <p className="text-[11px] text-slate-600 mt-1">
              Run a natural language prompt or upload an image snippet to find matching satellite tiles.
            </p>
          </div>
        )}

        {results.map((item) => {
          const scorePercent = Math.round(item.similarity_score * 100);
          return (
            <div
              key={item.tile_id}
              className="p-3 rounded-lg bg-slate-900/90 border border-slate-800 hover:border-slate-700 transition flex flex-col gap-2"
            >
              {/* Tile header: score badge + ID */}
              <div className="flex items-center justify-between">
                <span className="font-mono text-slate-300 text-[11px] font-semibold">
                  Tile {item.tile_id.slice(0, 8)}...
                </span>
                <span
                  className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold ${
                    scorePercent >= 75
                      ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                      : scorePercent >= 45
                      ? "bg-sky-500/20 text-sky-400 border border-sky-500/30"
                      : "bg-slate-800 text-slate-400 border border-slate-700"
                  }`}
                >
                  {scorePercent}% Match
                </span>
              </div>

              {/* Metadata */}
              <div className="grid grid-cols-2 gap-2 text-[10px] text-slate-400 font-mono">
                {item.metadata?.acquisition_date && (
                  <div className="flex items-center gap-1">
                    <Calendar className="w-3 h-3 text-slate-500" />
                    <span>{item.metadata.acquisition_date.slice(0, 10)}</span>
                  </div>
                )}
                {item.metadata?.cloud_cover !== undefined && (
                  <div className="flex items-center gap-1">
                    <Cloud className="w-3 h-3 text-slate-500" />
                    <span>Cloud: {item.metadata.cloud_cover.toFixed(1)}%</span>
                  </div>
                )}
                {item.metadata?.sensor && (
                  <div className="col-span-2 text-slate-500">
                    Sensor: {item.metadata.sensor}
                  </div>
                )}
              </div>

              {/* Action Buttons */}
              <div className="flex items-center justify-between gap-1.5 pt-1.5 border-t border-slate-800/80">
                <button
                  onClick={() => handleFindSimilar(item.tile_id)}
                  className="flex items-center gap-1 px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-[10px] transition"
                  title="Find visually similar tiles"
                >
                  <Sparkles className="w-3 h-3 text-sky-400" />
                  <span>Find Similar</span>
                </button>

                {onSelectForChange && (
                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => onSelectForChange(item.tile_id, "before")}
                      className="px-2 py-1 rounded bg-indigo-500/20 hover:bg-indigo-500/30 text-indigo-300 border border-indigo-500/30 text-[10px] transition"
                      title="Set as Before / Baseline tile"
                    >
                      Set T1 (Before)
                    </button>
                    <button
                      onClick={() => onSelectForChange(item.tile_id, "after")}
                      className="px-2 py-1 rounded bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 border border-emerald-500/30 text-[10px] transition"
                      title="Set as After / Comparison tile"
                    >
                      Set T2 (After)
                    </button>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
