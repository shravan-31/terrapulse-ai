/**
 * frontend/src/components/PipelineStepper.tsx
 * Real-time satellite imagery ingestion pipeline stepper.
 * Connects to the SSE endpoint /api/jobs/{id}/events (ADR-005).
 */

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  CheckCircle2,
  AlertTriangle,
  Loader2,
  XCircle,
  Layers,
  Download,
  Search,
  Grid,
} from "lucide-react";
import { useReducedMotion } from "../hooks/useReducedMotion";

export interface PipelineStepperProps {
  jobId: string;
  onComplete?: () => void;
  onDismiss?: () => void;
}

interface Step {
  id: string;
  label: string;
  icon: React.ReactNode;
}

const STEPS: Step[] = [
  { id: "catalog_search", label: "STAC Catalog Discovery", icon: <Search className="w-4 h-4" /> },
  { id: "downloading", label: "Asset Retrieval & Checksum", icon: <Download className="w-4 h-4" /> },
  { id: "preprocessing", label: "Reflectance & SCL Mask", icon: <Layers className="w-4 h-4" /> },
  { id: "tiling", label: "256x256 Grid Tiling", icon: <Grid className="w-4 h-4" /> },
  { id: "completed", label: "Ingestion Ready", icon: <CheckCircle2 className="w-4 h-4" /> },
];

export const PipelineStepper: React.FC<PipelineStepperProps> = ({
  jobId,
  onComplete,
  onDismiss,
}) => {
  const shouldReduceMotion = useReducedMotion();
  const [currentStepIndex, setCurrentStepIndex] = useState(0);
  const [progress, setProgress] = useState(0);
  const [status, setStatus] = useState<"running" | "completed" | "failed">("running");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [latestMessage, setLatestMessage] = useState("Connecting to ingestion event stream...");

  useEffect(() => {
    if (!jobId) return;

    const eventSource = new EventSource(`/api/jobs/${jobId}/events`);

    const handleEvent = (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data);
        if (data.message) {
          setLatestMessage(data.message);
        }

        // Determine step index based on event type or event_data.stage
        const stage = data.event_data?.stage || data.event_type;
        if (stage === "catalog_search") {
          setCurrentStepIndex(0);
          setProgress(20);
        } else if (stage === "scenes_discovered" || stage === "downloading") {
          setCurrentStepIndex(1);
          setProgress(40);
        } else if (stage === "preprocessing") {
          setCurrentStepIndex(2);
          setProgress(65);
        } else if (stage === "tiling") {
          setCurrentStepIndex(3);
          setProgress(85);
        } else if (data.event_type === "completed") {
          setCurrentStepIndex(4);
          setProgress(100);
          setStatus("completed");
          if (onComplete) onComplete();
          eventSource.close();
        } else if (data.event_type === "failed") {
          setStatus("failed");
          setErrorMessage(data.message || "Ingestion pipeline encountered a failure.");
          eventSource.close();
        }
      } catch (err) {
        // SSE heartbeat or unparseable event
      }
    };

    eventSource.onmessage = handleEvent;
    eventSource.addEventListener("stage_started", handleEvent);
    eventSource.addEventListener("scenes_discovered", handleEvent);
    eventSource.addEventListener("downloading", handleEvent);
    eventSource.addEventListener("tiling", handleEvent);
    eventSource.addEventListener("completed", handleEvent);
    eventSource.addEventListener("failed", handleEvent);

    eventSource.onerror = () => {
      // Reconnection or close
    };

    return () => {
      eventSource.close();
    };
  }, [jobId, onComplete]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.95 }}
      transition={{ duration: shouldReduceMotion ? 0 : 0.2 }}
      className="bg-slate-900/90 backdrop-blur-md border border-slate-700/60 rounded-xl p-4 shadow-xl text-slate-100 w-full max-w-md"
    >
      <div className="flex items-center justify-between mb-3 border-b border-slate-800 pb-2">
        <div className="flex items-center gap-2">
          {status === "running" && (
            <Loader2 className="w-4 h-4 text-emerald-400 animate-spin" />
          )}
          {status === "completed" && (
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          )}
          {status === "failed" && (
            <XCircle className="w-4 h-4 text-rose-400" />
          )}
          <span className="font-semibold text-sm tracking-wide">
            Satellite Pipeline {status === "running" ? `(${Math.round(progress)}%)` : ""}
          </span>
        </div>
        {onDismiss && (
          <button
            onClick={onDismiss}
            className="text-xs text-slate-400 hover:text-slate-200 px-2 py-0.5 rounded hover:bg-slate-800"
          >
            Dismiss
          </button>
        )}
      </div>

      {/* Progress bar */}
      <div className="w-full bg-slate-800 rounded-full h-1.5 mb-4 overflow-hidden">
        <div
          className={`h-full transition-all duration-300 ${
            status === "failed"
              ? "bg-rose-500"
              : status === "completed"
              ? "bg-emerald-500"
              : "bg-emerald-400"
          }`}
          style={{ width: `${progress}%` }}
        />
      </div>

      {/* Steps vertical list */}
      <div className="space-y-2 mb-3">
        {STEPS.map((step, idx) => {
          const isDone = idx < currentStepIndex || status === "completed";
          const isCurrent = idx === currentStepIndex && status === "running";
          const isFailed = idx === currentStepIndex && status === "failed";

          return (
            <div
              key={step.id}
              className={`flex items-center gap-3 px-2 py-1.5 rounded-lg text-xs transition-colors ${
                isCurrent
                  ? "bg-slate-800/80 text-emerald-300 font-medium"
                  : isDone
                  ? "text-slate-300"
                  : isFailed
                  ? "bg-rose-950/40 text-rose-300 font-medium"
                  : "text-slate-500"
              }`}
            >
              <div
                className={`p-1 rounded-md ${
                  isDone
                    ? "bg-emerald-500/20 text-emerald-400"
                    : isCurrent
                    ? "bg-emerald-500/30 text-emerald-300"
                    : isFailed
                    ? "bg-rose-500/20 text-rose-400"
                    : "bg-slate-800 text-slate-500"
                }`}
              >
                {step.icon}
              </div>
              <span className="flex-1">{step.label}</span>
              {isDone && <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />}
              {isCurrent && <Loader2 className="w-3.5 h-3.5 animate-spin text-emerald-400" />}
              {isFailed && <AlertTriangle className="w-3.5 h-3.5 text-rose-400" />}
            </div>
          );
        })}
      </div>

      {/* Current message */}
      <div className="text-[11px] text-slate-400 bg-slate-950/50 p-2 rounded-lg border border-slate-800/80 truncate">
        {errorMessage ? (
          <span className="text-rose-400">{errorMessage}</span>
        ) : (
          <span>{latestMessage}</span>
        )}
      </div>
    </motion.div>
  );
};
