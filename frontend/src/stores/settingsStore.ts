/**
 * frontend/src/stores/settingsStore.ts
 * Zustand store for user-configurable settings, persisted to localStorage.
 *
 * Settings:
 * - reduceAnimations: user toggle (separate from OS prefers-reduced-motion)
 * - operatorUsername / operatorPassword: stored in session only (never persisted to localStorage)
 */

import { create } from "zustand";
import { persist } from "zustand/middleware";

interface SettingsState {
  // UI preferences (persisted)
  reduceAnimations: boolean;

  // Session credentials (NOT persisted — only in memory during session)
  operatorUsername: string;
  operatorPassword: string;

  // Actions
  setReduceAnimations: (v: boolean) => void;
  setCredentials: (username: string, password: string) => void;
}

export const useSettingsStore = create<SettingsState>()(
  persist(
    (set) => ({
      reduceAnimations: false,
      operatorUsername: "",
      operatorPassword: "",

      setReduceAnimations: (v) => set({ reduceAnimations: v }),
      setCredentials: (username, password) =>
        set({ operatorUsername: username, operatorPassword: password }),
    }),
    {
      name: "satquery-settings",
      // Only persist UI preferences — never credentials
      partialize: (state: SettingsState) => ({ reduceAnimations: state.reduceAnimations }),
    }
  )
);
