/**
 * frontend/src/components/AssistantPanel.tsx
 * Phase 10 & 11 — Factual Chat Assistant, Structured Reports & Immutable Audit Trail.
 */

import React, { useState } from "react";
import {
  MessageSquare,
  Send,
  Download,
  ShieldCheck,
  FileSpreadsheet,
  FileCode,
  Map,
  History,
  Loader2,
  AlertCircle,
} from "lucide-react";
import { askAssistant, downloadReport, fetchProvenance } from "../services/api";
import { AssistantCitation, ProvenanceRecord } from "../types";
import { useSettingsStore } from "../stores/settingsStore";
import { useMapStore } from "../stores/mapStore";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  citations?: AssistantCitation[];
}

export function AssistantPanel() {
  const { operatorUsername, operatorPassword } = useSettingsStore();
  const { activeAOI } = useMapStore();
  const creds = operatorUsername ? { username: operatorUsername, password: operatorPassword } : undefined;

  const [activeTab, setActiveTab] = useState<"chat" | "reports" | "provenance">("chat");

  // Chat State
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: "assistant",
      content:
        "Hello! I am your SatQuery AI Earth Observation Assistant. My answers are strictly grounded in verified database facts, telemetry, and change detections.",
    },
  ]);
  const [inputMessage, setInputMessage] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const [chatError, setChatError] = useState<string | null>(null);

  // Reports State
  const [downloadingFormat, setDownloadingFormat] = useState<string | null>(null);

  // Provenance State
  const [provenanceLoading, setProvenanceLoading] = useState(false);
  const [provenanceRecords, setProvenanceRecords] = useState<ProvenanceRecord[]>([]);

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputMessage.trim() || chatLoading) return;

    const userText = inputMessage.trim();
    setInputMessage("");
    setChatError(null);

    const newHistory: ChatMessage[] = [...messages, { role: "user", content: userText }];
    setMessages(newHistory);
    setChatLoading(true);

    try {
      const historyPayload = newHistory.map((m) => ({
        role: m.role,
        content: m.content,
      }));
      const res = await askAssistant(userText, activeAOI?.id, historyPayload, creds);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: res.reply,
          citations: res.citations,
        },
      ]);
    } catch (err: any) {
      setChatError(err.message || "Failed to reach assistant");
    } finally {
      setChatLoading(false);
    }
  };

  const handleDownload = async (format: "geojson" | "csv" | "json") => {
    setDownloadingFormat(format);
    try {
      const blob = await downloadReport(format, activeAOI?.id, creds);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `satquery_export_${activeAOI?.id ? activeAOI.id.slice(0, 8) : "all"}.${format}`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err: any) {
      alert(`Report download error: ${err.message}`);
    } finally {
      setDownloadingFormat(null);
    }
  };

  const handleLoadProvenance = async () => {
    setProvenanceLoading(true);
    try {
      const records = await fetchProvenance(undefined, creds);
      setProvenanceRecords(records);
    } catch (err: any) {
      console.error("Provenance error:", err);
    } finally {
      setProvenanceLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full gap-3 text-xs">
      {/* Sub Tabs */}
      <div className="flex items-center gap-1 border-b border-slate-800 pb-2 shrink-0">
        <button
          onClick={() => setActiveTab("chat")}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg font-medium transition ${
            activeTab === "chat"
              ? "bg-sky-500/20 text-sky-400 border border-sky-500/30"
              : "text-slate-400 hover:text-slate-200"
          }`}
        >
          <MessageSquare className="w-3.5 h-3.5" />
          <span>Factual Chat</span>
        </button>

        <button
          onClick={() => setActiveTab("reports")}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg font-medium transition ${
            activeTab === "reports"
              ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
              : "text-slate-400 hover:text-slate-200"
          }`}
        >
          <Download className="w-3.5 h-3.5" />
          <span>Export Reports</span>
        </button>

        <button
          onClick={() => {
            setActiveTab("provenance");
            handleLoadProvenance();
          }}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg font-medium transition ${
            activeTab === "provenance"
              ? "bg-indigo-500/20 text-indigo-400 border border-indigo-500/30"
              : "text-slate-400 hover:text-slate-200"
          }`}
        >
          <History className="w-3.5 h-3.5" />
          <span>Audit Lineage</span>
        </button>
      </div>

      {/* CHAT TAB */}
      {activeTab === "chat" && (
        <div className="flex-1 flex flex-col gap-2.5 overflow-hidden">
          {/* Grounding banner */}
          <div className="flex items-center gap-2 p-2 rounded-lg bg-sky-500/10 border border-sky-500/20 text-[10px] text-sky-300 shrink-0">
            <ShieldCheck className="w-4 h-4 text-sky-400 shrink-0" />
            <span>ADR-011 Zero Speculation: Grounded strictly by catalog and change evidence.</span>
          </div>

          {/* Messages list */}
          <div className="flex-1 overflow-y-auto space-y-3 pr-1">
            {messages.map((m, idx) => (
              <div
                key={idx}
                className={`flex flex-col gap-1 ${
                  m.role === "user" ? "items-end" : "items-start"
                }`}
              >
                <div
                  className={`p-3 rounded-2xl max-w-[90%] text-xs leading-relaxed ${
                    m.role === "user"
                      ? "bg-sky-600 text-white rounded-br-none"
                      : "bg-slate-900 border border-slate-800 text-slate-200 rounded-bl-none"
                  }`}
                >
                  <p className="whitespace-pre-wrap">{m.content}</p>

                  {/* Citations */}
                  {m.citations && m.citations.length > 0 && (
                    <div className="mt-2.5 pt-2 border-t border-slate-800 flex flex-col gap-1">
                      <span className="text-[10px] font-mono text-slate-400 uppercase font-semibold">
                        Citations & Evidence:
                      </span>
                      {m.citations.map((c, cIdx) => (
                        <div
                          key={cIdx}
                          className="flex items-center gap-1.5 text-[10px] font-mono text-sky-400 bg-sky-500/10 px-2 py-0.5 rounded border border-sky-500/20"
                        >
                          <span className="uppercase text-slate-400">{c.entity_type}:</span>
                          <span>{c.entity_id.slice(0, 12)}...</span>
                          {c.confidence && (
                            <span className="text-slate-400 ml-auto">
                              {Math.round(c.confidence * 100)}%
                            </span>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}

            {chatLoading && (
              <div className="flex items-center gap-2 text-slate-400 p-2 text-xs">
                <Loader2 className="w-4 h-4 animate-spin text-sky-400" />
                <span>Consulting verified catalog & change records...</span>
              </div>
            )}
          </div>

          {chatError && (
            <div className="p-2 rounded bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs shrink-0 flex items-center gap-2">
              <AlertCircle className="w-3.5 h-3.5 text-rose-400 shrink-0" />
              <span>{chatError}</span>
            </div>
          )}

          {/* Chat input */}
          <form onSubmit={handleSendMessage} className="flex gap-2 shrink-0">
            <input
              type="text"
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              placeholder="Ask about detected changes, timestamps, or AOI stats..."
              className="flex-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-sky-500 transition"
            />
            <button
              type="submit"
              disabled={chatLoading || !inputMessage.trim()}
              className="px-3 py-2 bg-sky-500 hover:bg-sky-400 text-slate-950 rounded-lg font-medium transition disabled:opacity-50 flex items-center justify-center"
            >
              <Send className="w-4 h-4" />
            </button>
          </form>
        </div>
      )}

      {/* REPORTS TAB */}
      {activeTab === "reports" && (
        <div className="flex-1 flex flex-col gap-4 overflow-y-auto">
          <div className="p-3 bg-slate-900/60 rounded-xl border border-slate-800 space-y-3">
            <h3 className="font-semibold text-slate-200">Export Analysis Reports</h3>
            <p className="text-[11px] text-slate-400">
              Generate fully standardized, formula-injection defended analytical packages for GIS, spreadsheets, or programmatic downstream pipelines.
            </p>

            <div className="space-y-2 pt-1">
              <button
                onClick={() => handleDownload("geojson")}
                disabled={Boolean(downloadingFormat)}
                className="w-full flex items-center justify-between p-3 rounded-lg bg-slate-900 border border-slate-700 hover:border-emerald-500/50 transition text-left"
              >
                <div className="flex items-center gap-2.5">
                  <Map className="w-4 h-4 text-emerald-400" />
                  <div>
                    <span className="font-medium text-slate-200 block">GeoJSON FeatureCollection</span>
                    <span className="text-[10px] text-slate-500">
                      Standard EPSG:4326 vector polygons ready for QGIS / ArcGIS
                    </span>
                  </div>
                </div>
                {downloadingFormat === "geojson" ? (
                  <Loader2 className="w-4 h-4 animate-spin text-emerald-400" />
                ) : (
                  <Download className="w-4 h-4 text-slate-400" />
                )}
              </button>

              <button
                onClick={() => handleDownload("csv")}
                disabled={Boolean(downloadingFormat)}
                className="w-full flex items-center justify-between p-3 rounded-lg bg-slate-900 border border-slate-700 hover:border-sky-500/50 transition text-left"
              >
                <div className="flex items-center gap-2.5">
                  <FileSpreadsheet className="w-4 h-4 text-sky-400" />
                  <div>
                    <span className="font-medium text-slate-200 block">CSV Tabular Export</span>
                    <span className="text-[10px] text-slate-500">
                      Sanitized CSV with formula injection defense for Excel / Sheets
                    </span>
                  </div>
                </div>
                {downloadingFormat === "csv" ? (
                  <Loader2 className="w-4 h-4 animate-spin text-sky-400" />
                ) : (
                  <Download className="w-4 h-4 text-slate-400" />
                )}
              </button>

              <button
                onClick={() => handleDownload("json")}
                disabled={Boolean(downloadingFormat)}
                className="w-full flex items-center justify-between p-3 rounded-lg bg-slate-900 border border-slate-700 hover:border-purple-500/50 transition text-left"
              >
                <div className="flex items-center gap-2.5">
                  <FileCode className="w-4 h-4 text-purple-400" />
                  <div>
                    <span className="font-medium text-slate-200 block">Full JSON Analytics</span>
                    <span className="text-[10px] text-slate-500">
                      Structured object schema with confidence calibrations and review logs
                    </span>
                  </div>
                </div>
                {downloadingFormat === "json" ? (
                  <Loader2 className="w-4 h-4 animate-spin text-purple-400" />
                ) : (
                  <Download className="w-4 h-4 text-slate-400" />
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* PROVENANCE TAB */}
      {activeTab === "provenance" && (
        <div className="flex-1 flex flex-col gap-2.5 overflow-hidden">
          <div className="flex items-center justify-between text-[11px] text-slate-400 border-b border-slate-800 pb-1.5 shrink-0">
            <span>Immutable Lineage Log</span>
            <button
              onClick={handleLoadProvenance}
              className="text-sky-400 hover:text-sky-300 font-mono text-[10px]"
            >
              Refresh
            </button>
          </div>

          <div className="flex-1 overflow-y-auto space-y-2 pr-1">
            {provenanceLoading && (
              <div className="flex items-center justify-center p-6 text-slate-500 gap-2">
                <Loader2 className="w-4 h-4 animate-spin text-sky-400" />
                <span>Reading tamper-evident provenance log...</span>
              </div>
            )}

            {!provenanceLoading && provenanceRecords.length === 0 && (
              <div className="h-36 flex flex-col items-center justify-center text-slate-500 text-center">
                <History className="w-8 h-8 text-slate-600 mb-1" />
                <p>No recorded provenance actions yet.</p>
              </div>
            )}

            {provenanceRecords.map((rec, idx) => (
              <div
                key={rec.id || idx}
                className="p-2.5 rounded-lg bg-slate-900 border border-slate-800 text-[10px] flex flex-col gap-1"
              >
                <div className="flex items-center justify-between font-mono">
                  <span className="text-sky-400 font-bold uppercase">{rec.action}</span>
                  <span className="text-slate-500">{rec.recorded_at?.slice(0, 19)}</span>
                </div>
                <div className="text-slate-400 font-mono">
                  Entity: <span className="text-slate-300">{rec.entity_id}</span>
                </div>
                <div className="text-slate-500 font-mono">
                  Agent: <span className="text-slate-400">{rec.agent_id}</span>
                </div>
                {rec.details_json && Object.keys(rec.details_json).length > 0 && (
                  <pre className="mt-1 p-1.5 rounded bg-slate-950 text-slate-400 text-[9px] font-mono overflow-x-auto">
                    {JSON.stringify(rec.details_json, null, 2)}
                  </pre>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
