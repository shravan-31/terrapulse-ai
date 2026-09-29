/**
 * frontend/src/components/ChangeAnalysisPanel.tsx
 * Phase 6 — Bi-Temporal Change Detection & Human-in-the-Loop Analyst Review.
 */

import { useState } from "react";
import {
  GitCompare,
  CheckCircle2,
  XCircle,
  Flag,
  AlertTriangle,
  Loader2,
  ShieldCheck,
} from "lucide-react";
import { runChangeAnalysis, reviewChange } from "../services/api";
import { ChangeAnalysisResponse, ReviewStatus } from "../types";
import { useSettingsStore } from "../stores/settingsStore";
import { useMapStore } from "../stores/mapStore";

interface ChangeAnalysisPanelProps {
  initialBeforeTileId?: string;
  initialAfterTileId?: string;
}

export function ChangeAnalysisPanel({
  initialBeforeTileId = "",
  initialAfterTileId = "",
}: ChangeAnalysisPanelProps) {
  const { activeAOI } = useMapStore();

  const [beforeTileId, setBeforeTileId] = useState(initialBeforeTileId);
  const [afterTileId, setAfterTileId] = useState(initialAfterTileId);
  const [baselineDate, setBaselineDate] = useState("2022-01-01");
  const [comparisonDate, setComparisonDate] = useState("2024-01-01");

  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [analysisResult, setAnalysisResult] = useState<ChangeAnalysisResponse | null>(null);
  const [reviewDecisions, setReviewDecisions] = useState<Record<string, ReviewStatus>>({});
  const [submittingReview, setSubmittingReview] = useState<Record<string, boolean>>({});

  const handleRunAnalysis = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!beforeTileId.trim() || !afterTileId.trim()) {
      setError("Please provide both Before (T1) and After (T2) tile IDs.");
      return;
    }

    setAnalyzing(true);
    setError(null);
    try {
      const res = await runChangeAnalysis({
        aoi_id: activeAOI?.id,
        before_tile_id: beforeTileId.trim(),
        after_tile_id: afterTileId.trim(),
        baseline_date: baselineDate,
        comparison_date: comparisonDate,
      });
      setAnalysisResult(res);
      // Pre-fill existing review statuses
      const existingReviews: Record<string, ReviewStatus> = {};
      res.changes.forEach((c) => {
        if (c.review_status) {
          existingReviews[c.id] = c.review_status;
        }
      });
      setReviewDecisions(existingReviews);
    } catch (err: any) {
      setError(err.message || "Change detection analysis failed");
    } finally {
      setAnalyzing(false);
    }
  };

  const handleReview = async (changeId: string, decision: ReviewStatus) => {
    setSubmittingReview((prev) => ({ ...prev, [changeId]: true }));
    try {
      await reviewChange(changeId, decision);
      setReviewDecisions((prev) => ({ ...prev, [changeId]: decision }));
    } catch (err: any) {
      console.error("Failed to record review:", err);
      alert(`Review error: ${err.message}`);
    } finally {
      setSubmittingReview((prev) => ({ ...prev, [changeId]: false }));
    }
  };

  return (
    <div className="flex flex-col h-full gap-4 text-xs">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-800 pb-2 shrink-0">
        <div className="flex items-center gap-2">
          <GitCompare className="w-4 h-4 text-emerald-400" />
          <span className="font-semibold text-slate-200">Bi-Temporal Analysis</span>
        </div>
        <span className="text-[10px] font-mono text-slate-400 bg-slate-800 px-2 py-0.5 rounded border border-slate-700">
          ChangeFormerV6
        </span>
      </div>

      {/* Tile Selection Form */}
      <form onSubmit={handleRunAnalysis} className="flex flex-col gap-3 shrink-0 bg-slate-900/60 p-3 rounded-xl border border-slate-800">
        <div>
          <label className="text-[10px] uppercase font-mono text-indigo-400 block mb-1">
            T1 · Before / Baseline Tile ID
          </label>
          <input
            type="text"
            value={beforeTileId}
            onChange={(e) => setBeforeTileId(e.target.value)}
            placeholder="e.g., tile-001 or UUID..."
            className="w-full bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-slate-100 font-mono placeholder-slate-600 focus:outline-none focus:border-indigo-500 transition"
          />
        </div>

        <div>
          <label className="text-[10px] uppercase font-mono text-emerald-400 block mb-1">
            T2 · After / Comparison Tile ID
          </label>
          <input
            type="text"
            value={afterTileId}
            onChange={(e) => setAfterTileId(e.target.value)}
            placeholder="e.g., tile-002 or UUID..."
            className="w-full bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-slate-100 font-mono placeholder-slate-600 focus:outline-none focus:border-emerald-500 transition"
          />
        </div>

        <div className="grid grid-cols-2 gap-2">
          <div>
            <label className="text-[10px] text-slate-400 block mb-1">Baseline Date</label>
            <input
              type="date"
              value={baselineDate}
              onChange={(e) => setBaselineDate(e.target.value)}
              className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-slate-200 text-[11px] font-mono"
            />
          </div>
          <div>
            <label className="text-[10px] text-slate-400 block mb-1">Comparison Date</label>
            <input
              type="date"
              value={comparisonDate}
              onChange={(e) => setComparisonDate(e.target.value)}
              className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-slate-200 text-[11px] font-mono"
            />
          </div>
        </div>

        {/* Hard QC note */}
        <div className="text-[10px] text-slate-500 flex items-center gap-1.5">
          <ShieldCheck className="w-3.5 h-3.5 text-sky-400 shrink-0" />
          <span>ADR-006 Hard QC Filter: Min 9 px & ≥ 900 m²</span>
        </div>

        <button
          type="submit"
          disabled={analyzing}
          className="w-full flex items-center justify-center gap-2 py-2 px-3 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-medium transition disabled:opacity-50"
        >
          {analyzing ? (
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
          ) : (
            <GitCompare className="w-3.5 h-3.5" />
          )}
          <span>{analyzing ? "Running ChangeFormer Inference..." : "Detect Changes"}</span>
        </button>
      </form>

      {/* Error state */}
      {error && (
        <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex gap-2 items-start shrink-0">
          <AlertTriangle className="w-4 h-4 shrink-0 text-rose-400 mt-0.5" />
          <span>{error}</span>
        </div>
      )}

      {/* Results Section */}
      {analysisResult && (
        <div className="flex-1 flex flex-col gap-2.5 overflow-hidden">
          <div className="flex items-center justify-between text-[11px] text-slate-400 border-b border-slate-800 pb-1.5 shrink-0">
            <span>
              Found <strong className="text-emerald-400">{analysisResult.total_changes}</strong> verified change polygons
            </span>
            <span className="font-mono text-[10px] text-slate-500">{analysisResult.duration_ms}ms</span>
          </div>

          <div className="flex-1 overflow-y-auto space-y-2.5 pr-1">
            {analysisResult.changes.length === 0 && (
              <div className="h-32 flex flex-col items-center justify-center text-slate-500 text-center">
                <p>No changes met the threshold and area criteria.</p>
              </div>
            )}

            {analysisResult.changes.map((change, idx) => {
              const currentDecision = reviewDecisions[change.id] || change.review_status;
              const isSubmitting = submittingReview[change.id];

              return (
                <div
                  key={change.id || idx}
                  className="p-3 rounded-xl bg-slate-900 border border-slate-800 hover:border-slate-700 transition flex flex-col gap-2"
                >
                  {/* Taxonomy Badges */}
                  <div className="flex items-center justify-between flex-wrap gap-1">
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 capitalize font-medium">
                      {change.change_type.replace(/_/g, " ")}
                    </span>
                    <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700 capitalize">
                      {change.change_kind}
                    </span>
                    <span
                      className={`text-[10px] font-mono px-2 py-0.5 rounded font-bold ${
                        change.temporal_status === "confirmed"
                          ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                          : "bg-amber-500/20 text-amber-400 border border-amber-500/30"
                      }`}
                    >
                      {change.temporal_status}
                    </span>
                  </div>

                  {/* Quantitative Metrics */}
                  <div className="grid grid-cols-3 gap-1 bg-slate-950/60 p-2 rounded-lg text-[10px] font-mono text-center">
                    <div>
                      <span className="text-slate-500 block">Area</span>
                      <span className="text-slate-200 font-semibold">{Math.round(change.area_m2)} m²</span>
                    </div>
                    <div>
                      <span className="text-slate-500 block">Pixels</span>
                      <span className="text-slate-200 font-semibold">{change.pixel_count} px</span>
                    </div>
                    <div>
                      <span className="text-slate-500 block">Confidence</span>
                      <span className="text-emerald-400 font-semibold">
                        {(change.confidence_score * 100).toFixed(0)}%
                      </span>
                    </div>
                  </div>

                  {/* Human Analyst Decision Section */}
                  <div className="pt-2 border-t border-slate-800 flex flex-col gap-1.5">
                    <div className="flex items-center justify-between text-[10px]">
                      <span className="text-slate-400 font-medium">Analyst Review:</span>
                      {currentDecision ? (
                        <span
                          className={`font-mono px-1.5 py-0.2 rounded font-semibold ${
                            currentDecision === "confirmed_by_analyst"
                              ? "text-emerald-400"
                              : currentDecision === "rejected_by_analyst"
                              ? "text-rose-400"
                              : "text-amber-400"
                          }`}
                        >
                          {currentDecision.toUpperCase()}
                        </span>
                      ) : (
                        <span className="text-slate-500 italic">Pending</span>
                      )}
                    </div>

                    <div className="flex items-center gap-1.5">
                      <button
                        onClick={() => handleReview(change.id, "confirmed_by_analyst")}
                        disabled={isSubmitting}
                        className={`flex-1 flex items-center justify-center gap-1 py-1 rounded text-[10px] font-medium transition ${
                          currentDecision === "confirmed_by_analyst"
                            ? "bg-emerald-500 text-slate-950 font-bold"
                            : "bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                        }`}
                        title="Confirm change"
                      >
                        <CheckCircle2 className="w-3 h-3" />
                        <span>Confirm</span>
                      </button>

                      <button
                        onClick={() => handleReview(change.id, "rejected_by_analyst")}
                        disabled={isSubmitting}
                        className={`flex-1 flex items-center justify-center gap-1 py-1 rounded text-[10px] font-medium transition ${
                          currentDecision === "rejected_by_analyst"
                            ? "bg-rose-500 text-slate-950 font-bold"
                            : "bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/30"
                        }`}
                        title="Reject as false positive"
                      >
                        <XCircle className="w-3 h-3" />
                        <span>Reject</span>
                      </button>

                      <button
                        onClick={() => handleReview(change.id, "flagged")}
                        disabled={isSubmitting}
                        className={`flex-1 flex items-center justify-center gap-1 py-1 rounded text-[10px] font-medium transition ${
                          currentDecision === "flagged"
                            ? "bg-amber-500 text-slate-950 font-bold"
                            : "bg-amber-500/10 hover:bg-amber-500/20 text-amber-400 border border-amber-500/30"
                        }`}
                        title="Flag for secondary review"
                      >
                        <Flag className="w-3 h-3" />
                        <span>Flag</span>
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
