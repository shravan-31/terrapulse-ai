/**
 * frontend/src/map/SatMap.tsx
 * High-Resolution Satellite & Street Basemap with Interactive AOI Drawing.
 *
 * Basemap Modes:
 * - 🛰️ Satellite Hybrid: High-resolution real satellite photography (ESRI World Imagery)
 *   with global city names, dams, reservoirs, lakes, borders, and highway labels.
 * - 🗺️ Streets: OpenStreetMap street and vector navigation map.
 */

import { useEffect, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

import { useMapStore } from "../stores/mapStore";
import { AOIRecord } from "../types";

interface SatMapProps {
  maptilerKey?: string;
  onAOIDrawn?: (polygon: GeoJSON.Polygon, name?: string) => void;
  className?: string;
}

const AOI_SOURCE_ID = "aoi-source";
const AOI_FILL_LAYER = "aoi-fill";
const AOI_OUTLINE_LAYER = "aoi-outline";
const DRAWING_SOURCE_ID = "drawing-source";
const DRAWING_FILL_LAYER = "drawing-fill";
const DRAWING_OUTLINE_LAYER = "drawing-outline";

// High-resolution multi-source basemap style definition
const BASEMAP_STYLE: maplibregl.StyleSpecification = {
  version: 8,
  sources: {
    "satellite-source": {
      type: "raster",
      tiles: [
        "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
      ],
      tileSize: 256,
      maxzoom: 19,
      attribution: "© Esri, Maxar, Earthstar Geographics",
    },
    "labels-source": {
      type: "raster",
      tiles: [
        "https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}",
      ],
      tileSize: 256,
      maxzoom: 19,
    },
    "streets-source": {
      type: "raster",
      tiles: [
        "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
      ],
      tileSize: 256,
      maxzoom: 19,
      attribution: "© OpenStreetMap contributors",
    },
  },
  layers: [
    {
      id: "streets-layer",
      type: "raster",
      source: "streets-source",
      layout: { visibility: "none" },
      minzoom: 0,
      maxzoom: 19,
    },
    {
      id: "satellite-layer",
      type: "raster",
      source: "satellite-source",
      layout: { visibility: "visible" },
      minzoom: 0,
      maxzoom: 19,
    },
    {
      id: "labels-layer",
      type: "raster",
      source: "labels-source",
      layout: { visibility: "visible" },
      minzoom: 0,
      maxzoom: 19,
    },
  ],
};

export function SatMap({ onAOIDrawn, className = "" }: SatMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const coordsPopupRef = useRef<HTMLSpanElement | null>(null);

  const [basemap, setBasemap] = useState<"satellite" | "streets">("satellite");

  const {
    mapLoaded,
    setMapLoaded,
    drawMode,
    aoiList,
    activeAOI,
    setDrawingCoords,
    clearDrawing,
    setActiveAOI,
  } = useMapStore();

  const drawingCoordsRef = useRef<[number, number][]>([]);
  const drawModeRef = useRef(drawMode);
  drawModeRef.current = drawMode;
  const onAOIDrawnRef = useRef(onAOIDrawn);
  onAOIDrawnRef.current = onAOIDrawn;

  // -------------------------------------------------------------------------
  // Map initialization with high-resolution satellite imagery
  // -------------------------------------------------------------------------
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: BASEMAP_STYLE,
      center: [78.9629, 20.5937], // India center
      zoom: 5,
      maxZoom: 19,
      attributionControl: false,
    });

    map.addControl(new maplibregl.NavigationControl({ showCompass: true }), "top-right");
    map.addControl(new maplibregl.ScaleControl({ maxWidth: 120, unit: "metric" }), "bottom-right");
    map.addControl(new maplibregl.AttributionControl({ compact: true }), "bottom-right");

    map.on("load", () => {
      // AOI persisted layers
      map.addSource(AOI_SOURCE_ID, {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
      });
      map.addLayer({
        id: AOI_FILL_LAYER,
        type: "fill",
        source: AOI_SOURCE_ID,
        paint: {
          "fill-color": [
            "case",
            ["boolean", ["feature-state", "active"], false],
            "#38bdf8",
            "#818cf8",
          ],
          "fill-opacity": [
            "case",
            ["boolean", ["feature-state", "active"], false],
            0.35,
            0.2,
          ],
        },
      });
      map.addLayer({
        id: AOI_OUTLINE_LAYER,
        type: "line",
        source: AOI_SOURCE_ID,
        paint: {
          "line-color": [
            "case",
            ["boolean", ["feature-state", "active"], false],
            "#38bdf8",
            "#818cf8",
          ],
          "line-width": [
            "case",
            ["boolean", ["feature-state", "active"], false],
            2.5,
            1.8,
          ],
          "line-opacity": 0.95,
        },
      });

      // Drawing preview layers
      map.addSource(DRAWING_SOURCE_ID, {
        type: "geojson",
        data: { type: "FeatureCollection", features: [] },
      });
      map.addLayer({
        id: DRAWING_FILL_LAYER,
        type: "fill",
        source: DRAWING_SOURCE_ID,
        paint: { "fill-color": "#38bdf8", "fill-opacity": 0.25 },
      });
      map.addLayer({
        id: DRAWING_OUTLINE_LAYER,
        type: "line",
        source: DRAWING_SOURCE_ID,
        paint: { "line-color": "#38bdf8", "line-width": 2.5, "line-dasharray": [4, 2] },
      });

      setMapLoaded(true);
    });

    // Mouse interaction — cursor change and coordinate readout
    map.on("mousemove", (e) => {
      const { lng, lat } = e.lngLat;
      if (coordsPopupRef.current) {
        coordsPopupRef.current.textContent = `${lat.toFixed(5)}°N, ${lng.toFixed(5)}°E`;
      }
      if (drawModeRef.current !== "none") {
        map.getCanvas().style.cursor = "crosshair";
        if (drawModeRef.current === "polygon" && drawingCoordsRef.current.length > 0) {
          _updateDrawingPreview(map, [...drawingCoordsRef.current, [lng, lat]]);
        }
      } else {
        map.getCanvas().style.cursor = "";
      }
    });

    // Click to add polygon vertices
    map.on("click", (e) => {
      if (drawModeRef.current !== "polygon") return;
      const { lng, lat } = e.lngLat;
      drawingCoordsRef.current = [...drawingCoordsRef.current, [lng, lat]];
      setDrawingCoords([...drawingCoordsRef.current]);
      _updateDrawingPreview(map, drawingCoordsRef.current);
    });

    // Double-click to close polygon
    map.on("dblclick", (e) => {
      e.preventDefault();
      if (drawModeRef.current !== "polygon") return;
      if (drawingCoordsRef.current.length < 3) return;

      const coords = drawingCoordsRef.current;
      const closed = [...coords, coords[0]] as [number, number][];
      const polygon: GeoJSON.Polygon = {
        type: "Polygon",
        coordinates: [closed.map(([lng, lat]) => [lng, lat])],
      };
      onAOIDrawnRef.current?.(polygon);
      drawingCoordsRef.current = [];
      clearDrawing();
      _clearDrawingPreview(map);
    });

    // AOI feature click — set active
    map.on("click", AOI_FILL_LAYER, (e) => {
      const features = map.queryRenderedFeatures(e.point, { layers: [AOI_FILL_LAYER] });
      if (features.length > 0) {
        const feat = features[0];
        const id = feat.properties?.id as string;
        const foundAOI = useMapStore.getState().aoiList.find((a: AOIRecord) => a.id === id) ?? null;
        setActiveAOI(foundAOI);
      }
    });

    mapRef.current = map;

    // ResizeObserver
    if (containerRef.current) {
      const observer = new ResizeObserver(() => {
        mapRef.current?.resize();
      });
      observer.observe(containerRef.current);
      return () => {
        observer.disconnect();
        map.remove();
        mapRef.current = null;
      };
    }

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // -------------------------------------------------------------------------
  // Handle Basemap Switch (Satellite vs Streets)
  // -------------------------------------------------------------------------
  const switchBasemap = (mode: "satellite" | "streets") => {
    const map = mapRef.current;
    if (!map || !mapLoaded) return;
    setBasemap(mode);

    if (mode === "satellite") {
      map.setLayoutProperty("satellite-layer", "visibility", "visible");
      map.setLayoutProperty("labels-layer", "visibility", "visible");
      map.setLayoutProperty("streets-layer", "visibility", "none");
    } else {
      map.setLayoutProperty("satellite-layer", "visibility", "none");
      map.setLayoutProperty("labels-layer", "visibility", "none");
      map.setLayoutProperty("streets-layer", "visibility", "visible");
    }
  };

  // -------------------------------------------------------------------------
  // Sync AOI list to map source
  // -------------------------------------------------------------------------
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapLoaded) return;

    const source = map.getSource(AOI_SOURCE_ID) as maplibregl.GeoJSONSource | undefined;
    if (!source) return;

    const fc: GeoJSON.FeatureCollection = {
      type: "FeatureCollection",
      features: aoiList.map((aoi) => ({
        type: "Feature",
        id: aoi.id,
        properties: { id: aoi.id, name: aoi.name, area_km2: aoi.area_km2 },
        geometry: aoi.geometry,
      })),
    };
    source.setData(fc);

    aoiList.forEach((aoi) => {
      map.setFeatureState(
        { source: AOI_SOURCE_ID, id: aoi.id },
        { active: activeAOI?.id === aoi.id }
      );
    });
  }, [aoiList, activeAOI, mapLoaded]);

  // Cursor style based on drawMode
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    if (drawMode !== "none") {
      drawingCoordsRef.current = [];
      map.getCanvas().style.cursor = "crosshair";
    } else {
      map.getCanvas().style.cursor = "";
    }
  }, [drawMode]);

  return (
    <div className={`relative w-full h-full ${className}`}>
      {/* Map container */}
      <div ref={containerRef} className="absolute inset-0" />

      {/* Basemap Switcher (Satellite vs Streets) */}
      <div className="absolute top-3 right-14 z-10 flex items-center bg-slate-900/90 border border-slate-700/80 rounded-lg p-1 backdrop-blur-md shadow-xl text-xs gap-1">
        <button
          onClick={() => switchBasemap("satellite")}
          className={`px-3 py-1.5 rounded-md font-medium flex items-center gap-1.5 transition ${
            basemap === "satellite"
              ? "bg-sky-500 text-slate-950 font-bold shadow"
              : "text-slate-400 hover:text-slate-200"
          }`}
          title="High-Resolution Real Satellite Photography with City & Dam Labels"
        >
          <span>🛰️ Satellite (सॅटेलाइट)</span>
        </button>
        <button
          onClick={() => switchBasemap("streets")}
          className={`px-3 py-1.5 rounded-md font-medium flex items-center gap-1.5 transition ${
            basemap === "streets"
              ? "bg-sky-500 text-slate-950 font-bold shadow"
              : "text-slate-400 hover:text-slate-200"
          }`}
          title="OpenStreetMap Streets & City Names"
        >
          <span>🗺️ Streets (रस्ते)</span>
        </button>
      </div>

      {/* Coordinate readout */}
      <div
        className="absolute bottom-8 left-3 z-10 px-2.5 py-1 rounded bg-slate-900/90 border border-slate-700/60 text-[10px] font-mono text-slate-300 pointer-events-none shadow"
        aria-live="polite"
        aria-label="Map coordinates"
      >
        <span ref={coordsPopupRef}>—°N, —°E</span>
      </div>

      {/* Draw mode indicator */}
      {drawMode !== "none" && (
        <div className="absolute top-3 left-1/2 -translate-x-1/2 z-10 px-3.5 py-1.5 rounded-full bg-sky-500/20 border border-sky-500/50 text-sky-300 text-xs font-semibold pointer-events-none backdrop-blur-md shadow-lg">
          {drawMode === "polygon"
            ? "Click to add vertices · Double-click to close polygon"
            : "Click and drag to draw rectangle"}
        </div>
      )}
    </div>
  );
}

function _updateDrawingPreview(map: maplibregl.Map, coords: [number, number][]) {
  const src = map.getSource(DRAWING_SOURCE_ID) as maplibregl.GeoJSONSource | undefined;
  if (!src || coords.length < 2) return;

  const ring = [...coords, coords[0]];
  src.setData({
    type: "FeatureCollection",
    features: [
      {
        type: "Feature",
        properties: {},
        geometry: { type: "Polygon", coordinates: [ring.map(([lng, lat]) => [lng, lat])] },
      },
    ],
  });
}

function _clearDrawingPreview(map: maplibregl.Map) {
  const src = map.getSource(DRAWING_SOURCE_ID) as maplibregl.GeoJSONSource | undefined;
  src?.setData({ type: "FeatureCollection", features: [] });
}
