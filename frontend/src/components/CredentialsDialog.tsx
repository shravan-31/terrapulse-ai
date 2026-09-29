/**
 * frontend/src/components/CredentialsDialog.tsx
 * Modal dialog for entering operator credentials.
 *
 * Credentials are stored in session memory only (settingsStore.operatorUsername/Password)
 * and never written to localStorage.
 *
 * Shown when credentials are empty or authentication fails.
 */

import React, { useState } from "react";
import { motion } from "framer-motion";
import { ShieldCheck, Eye, EyeOff, LogIn } from "lucide-react";
import { useSettingsStore } from "../stores/settingsStore";
import { fadeIn } from "../motion/tokens";

interface CredentialsDialogProps {
  onDismiss?: () => void;
}

export function CredentialsDialog({ onDismiss }: CredentialsDialogProps) {
  const { setCredentials } = useSettingsStore();
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!username || !password) return;
    setCredentials(username, password);
    onDismiss?.();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <motion.div
        variants={fadeIn}
        initial="hidden"
        animate="visible"
        className="w-full max-w-sm mx-4 bg-[#131B2E] border border-slate-700 rounded-2xl shadow-2xl p-6"
        role="dialog"
        aria-labelledby="creds-dialog-title"
        aria-modal="true"
      >
        <div className="flex items-center gap-3 mb-5">
          <div className="p-2 rounded-xl bg-sky-500/20 text-sky-400 border border-sky-500/30">
            <ShieldCheck className="w-5 h-5" />
          </div>
          <div>
            <h2 id="creds-dialog-title" className="text-sm font-semibold text-slate-100">
              Operator Authentication
            </h2>
            <p className="text-[11px] text-slate-400">
              Credentials are session-only and never stored locally.
            </p>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <div className="flex flex-col gap-1">
            <label htmlFor="creds-username" className="text-[11px] text-slate-400 uppercase tracking-wider">
              Username
            </label>
            <input
              id="creds-username"
              type="text"
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-sky-500 transition"
              required
            />
          </div>

          <div className="flex flex-col gap-1">
            <label htmlFor="creds-password" className="text-[11px] text-slate-400 uppercase tracking-wider">
              Password
            </label>
            <div className="relative">
              <input
                id="creds-password"
                type={showPassword ? "text" : "password"}
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 pr-9 text-sm text-slate-100 focus:outline-none focus:border-sky-500 transition"
                required
              />
              <button
                type="button"
                onClick={() => setShowPassword((v) => !v)}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 transition"
                aria-label={showPassword ? "Hide password" : "Show password"}
              >
                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>

          <button
            id="creds-submit-btn"
            type="submit"
            disabled={!username || !password}
            className="mt-1 flex items-center justify-center gap-2 py-2.5 rounded-xl bg-sky-500 hover:bg-sky-400 text-slate-950 font-semibold text-sm transition disabled:opacity-50"
          >
            <LogIn className="w-4 h-4" />
            Sign In
          </button>
        </form>
      </motion.div>
    </div>
  );
}
