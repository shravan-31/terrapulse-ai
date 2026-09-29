/**
 * frontend/src/App.tsx
 * TerraPulse AI — Autonomous Geospatial Intelligence & Change Detection Platform
 *
 * Theme: Obsidian Deep Space & Electric Indigo / Cyber-Emerald
 * Modules:
 * - Mission View: Landing page with 3D Earth simulation, key specs, architecture stack.
 * - Overview View: Surveillance Mission Control with GPS auto-detect, 63 monitored sectors, telemetry.
 * - Investigation View: 3-column workspace with Sentinel-2 passes, interactive Swipe Splitter, False Color NIR, AI Agent Report & Q&A, Analyst Verification.
 * - Semantic AI View: Natural-Language Earth Query with FAISS vector catalog and spatial plotting.
 */

import React, { useState, useEffect } from "react";
import {
  Compass,
  Search,
  Sparkles,
  ShieldCheck,
  Activity,
  Settings,
  Plus,
  Sliders,
  Radio,
  Layers,
} from "lucide-react";

import { MissionView } from "./components/terrapulse/MissionView";
import { OverviewView } from "./components/terrapulse/OverviewView";
import { InvestigationView, InvestigationTarget } from "./components/terrapulse/InvestigationView";
import { SemanticSearchView } from "./components/terrapulse/SemanticSearchView";
import { fetchHealth } from "./services/api";
import { SystemHealth } from "./types";
import { useSettingsStore } from "./stores/settingsStore";

export function App() {
  const [activeView, setActiveView] = useState<"mission" | "console" | "investigate" | "search">(
    "investigate"
  );
  const [activeTarget, setActiveTarget] = useState<InvestigationTarget | undefined>(undefined);
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [showSettings, setShowSettings] = useState(false);

  const { reduceAnimations, setReduceAnimations } = useSettingsStore();

  useEffect(() => {
    fetchHealth()
      .then((data) => setHealth(data))
      .catch(() => {});
  }, []);

  const handleInvestigateTarget = (target: InvestigationTarget) => {
    setActiveTarget(target);
    setActiveView("investigate");
  };

  return (
    <div className="flex flex-col h-screen w-screen bg-[#060913] text-slate-100 overflow-hidden select-none font-sans">
      {/* Top Header */}
      <header className="h-14 border-b border-indigo-950/60 bg-[#0b0f20]/95 backdrop-blur-md px-5 flex items-center justify-between z-30 shrink-0">
        {/* Left Branding */}
        <div className="flex items-center gap-3">
          <div
            onClick={() => setActiveView("mission")}
            className="flex items-center gap-2.5 cursor-pointer group"
          >
            {/* Custom Modern Logo: Glowing Aperture Radar in Electric Indigo & Emerald */}
            <div className="relative w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500/20 to-purple-600/20 border border-indigo-400/40 flex items-center justify-center text-indigo-400 shadow-[0_0_15px_rgba(99,102,241,0.35)] group-hover:scale-105 transition">
              <Radio className="w-4 h-4 text-indigo-300" />
              <span className="absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full bg-emerald-400 shadow-[0_0_6px_#34d399]" />
            </div>

            <div>
              <div className="flex items-center gap-2">
                <span className="text-base font-black tracking-wider text-white font-mono group-hover:text-indigo-300 transition">
                  TerraPulse<span className="text-indigo-400">.AI</span>
                </span>
                <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-indigo-950/80 border border-indigo-700/60 text-indigo-300 uppercase font-semibold">
                  ENTERPRISE
                </span>
              </div>
              <p className="text-[10px] text-slate-400 tracking-wider">
                Autonomous Earth Observation & Change Intelligence
              </p>
            </div>
          </div>
        </div>

        {/* Center Primary Navigation */}
        <nav className="flex items-center gap-1 bg-slate-900/90 p-1 rounded-xl border border-indigo-950/70 shadow-inner">
          <button
            id="nav-mission"
            onClick={() => setActiveView("mission")}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-medium transition flex items-center gap-1.5 ${
              activeView === "mission"
                ? "bg-gradient-to-r from-indigo-600 to-indigo-500 text-white font-bold shadow-[0_0_12px_rgba(99,102,241,0.5)]"
                : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
            }`}
          >
            <Compass className="w-3.5 h-3.5 text-indigo-300" />
            <span>Mission</span>
          </button>

          <button
            id="nav-console"
            onClick={() => setActiveView("console")}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-medium transition flex items-center gap-1.5 ${
              activeView === "console"
                ? "bg-gradient-to-r from-indigo-600 to-indigo-500 text-white font-bold shadow-[0_0_12px_rgba(99,102,241,0.5)]"
                : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
            }`}
          >
            <Activity className="w-3.5 h-3.5 text-indigo-300" />
            <span>Overview</span>
          </button>

          <button
            id="nav-investigate"
            onClick={() => setActiveView("investigate")}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-medium transition flex items-center gap-1.5 ${
              activeView === "investigate"
                ? "bg-gradient-to-r from-indigo-600 to-indigo-500 text-white font-bold shadow-[0_0_12px_rgba(99,102,241,0.5)]"
                : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
            }`}
          >
            <Search className="w-3.5 h-3.5 text-indigo-300" />
            <span>Investigation</span>
          </button>

          <button
            id="nav-search"
            onClick={() => setActiveView("search")}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-medium transition flex items-center gap-1.5 ${
              activeView === "search"
                ? "bg-gradient-to-r from-indigo-600 to-indigo-500 text-white font-bold shadow-[0_0_12px_rgba(99,102,241,0.5)]"
                : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
            }`}
          >
            <Sparkles className="w-3.5 h-3.5 text-purple-300" />
            <span>Semantic AI</span>
          </button>
        </nav>

        {/* Right Actions & Telemetry */}
        <div className="flex items-center gap-3">
          {/* New Scan Action */}
          <button
            id="btn-new-scan"
            onClick={() => setActiveView("investigate")}
            className="hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-indigo-600/20 hover:bg-indigo-600/30 border border-indigo-500/40 text-indigo-200 text-xs font-semibold transition shadow-[0_0_10px_rgba(99,102,241,0.2)]"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>New Scan</span>
          </button>

          {/* Telemetry Status Badge */}
          <div className="hidden lg:flex items-center gap-2 px-3 py-1 rounded-full bg-slate-900/90 border border-indigo-950 text-[11px] font-mono text-slate-300 shadow-sm">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse shadow-[0_0_8px_#34d399]" />
            <span>63 Sectors · 352 Changes · LIVE TELEMETRY</span>
          </div>

          {/* Settings button */}
          <button
            id="btn-settings"
            onClick={() => setShowSettings(!showSettings)}
            className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-slate-200 transition"
            aria-label="Settings"
          >
            <Settings className="w-4 h-4" />
          </button>
        </div>
      </header>

      {/* Settings Dialog Dropdown */}
      {showSettings && (
        <div className="absolute top-14 right-4 z-40 bg-[#0d1324] border border-indigo-900/60 rounded-xl shadow-2xl p-4 w-72 flex flex-col gap-3">
          <div className="flex items-center justify-between border-b border-slate-800 pb-2">
            <span className="text-xs font-semibold text-slate-200 uppercase tracking-wider">
              System Settings
            </span>
            <span className="text-[10px] font-mono text-indigo-400">v2.4.0</span>
          </div>

          <label className="flex items-center justify-between text-xs text-slate-300 cursor-pointer">
            <span>Reduce UI animations</span>
            <input
              type="checkbox"
              checked={reduceAnimations}
              onChange={(e) => setReduceAnimations(e.target.checked)}
              className="accent-indigo-500 w-4 h-4"
            />
          </label>

          <div className="text-[11px] text-slate-400 flex flex-col gap-1 pt-1 border-t border-slate-800">
            <div className="flex justify-between">
              <span>Sentinel-2 API:</span>
              <span className="text-emerald-400 font-mono">Connected</span>
            </div>
            <div className="flex justify-between">
              <span>PostGIS Vector DB:</span>
              <span className="text-emerald-400 font-mono">Ready</span>
            </div>
            <div className="flex justify-between">
              <span>ChangeFormer V6:</span>
              <span className="text-emerald-400 font-mono">Inference Active</span>
            </div>
          </div>
        </div>
      )}

      {/* Main Workspace Display */}
      <main className="flex-1 flex overflow-hidden relative">
        {activeView === "mission" && <MissionView onNavigate={(view) => setActiveView(view)} />}
        {activeView === "console" && (
          <OverviewView onInvestigateTarget={handleInvestigateTarget} />
        )}
        {activeView === "investigate" && <InvestigationView initialTarget={activeTarget} />}
        {activeView === "search" && (
          <SemanticSearchView onInvestigateTarget={handleInvestigateTarget} />
        )}
      </main>
    </div>
  );
}

export default App;
