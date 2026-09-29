/**
 * frontend/src/stores/mapStore.ts
 * Zustand store for map state.
 *
 * Manages:
 * - mapLoaded flag (set true when MapLibre fires 'load')
 * - drawMode: current AOI drawing mode (rectangle | polygon | none)
 * - aoiList: list of persisted AOIs
 * - activeAOI: currently selected/active AOI
 */

import { create } from "zustand";
import { AOIRecord, AOIDrawMode } from "../types";

interface MapStoreState {
  mapLoaded: boolean;
  drawMode: AOIDrawMode;
  aoiList: AOIRecord[];
  activeAOI: AOIRecord | null;
  drawingCoords: [number, number][] | null; // raw coordinates being drawn

  // Actions
  setMapLoaded: (loaded: boolean) => void;
  setDrawMode: (mode: AOIDrawMode) => void;
  addAOI: (aoi: AOIRecord) => void;
  setAOIs: (aois: AOIRecord[]) => void;
  setActiveAOI: (aoi: AOIRecord | null) => void;
  setDrawingCoords: (coords: [number, number][] | null) => void;
  clearDrawing: () => void;
}

export const useMapStore = create<MapStoreState>((set) => ({
  mapLoaded: false,
  drawMode: "none",
  aoiList: [],
  activeAOI: null,
  drawingCoords: null,

  setMapLoaded: (loaded) => set({ mapLoaded: loaded }),
  setDrawMode: (mode) => set({ drawMode: mode, drawingCoords: null }),
  addAOI: (aoi: AOIRecord) => set((s: MapStoreState) => ({ aoiList: [aoi, ...s.aoiList], activeAOI: aoi })),
  setAOIs: (aois) => set({ aoiList: aois }),
  setActiveAOI: (aoi) => set({ activeAOI: aoi }),
  setDrawingCoords: (coords) => set({ drawingCoords: coords }),
  clearDrawing: () => set({ drawingCoords: null, drawMode: "none" }),
}));
