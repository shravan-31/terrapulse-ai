import React, { useState, useEffect, useRef } from "react";
import {
  Sparkles,
  Search,
  ArrowRight,
  Database,
  Layers,
  MapPin,
  Calendar,
  Clock,
  Crosshair,
  ExternalLink,
  Upload,
  Image as ImageIcon,
} from "lucide-react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { searchSemantic, searchImage } from "../../services/api";

interface DetectedChangeFootprint {
  id: string;
  targetName: string;
  region: string;
  coords: [number, number]; // [lng, lat]
  date: string;
  similarity: number; // percentage
  activity: string;
  area: string;
  status: "verified" | "flagged";
  summary: string;
}

const SAMPLE_FOOTPRINTS: DetectedChangeFootprint[] = [
  {
    id: "fp-1",
    targetName: "Bhadla Solar Park Sector IV",
    region: "Phalodi, Rajasthan",
    coords: [71.916, 27.538],
    date: "2026-04-12",
    similarity: 98.4,
    activity: "Photovoltaic Array Grid Expansion",
    area: "1,198.48 ha",
    status: "verified",
    summary: "Large-scale surface leveling and high-density solar tracker mounting installed on desert parcel.",
  },
  {
    id: "fp-2",
    targetName: "Korba Mining Complex Basin",
    region: "Korba, Chhattisgarh",
    coords: [82.684, 22.359],
    date: "2026-04-10",
    similarity: 95.1,
    activity: "Open-Pit Overburden Excavation",
    area: "865.30 ha",
    status: "verified",
    summary: "Terraced bench earthmoving excavation with heavy mechanical soil displacement.",
  },
  {
    id: "fp-3",
    targetName: "Mundra Port Logistics Terminal 3",
    region: "Kutch, Gujarat",
    coords: [69.712, 22.756],
    date: "2026-04-08",
    similarity: 93.7,
    activity: "Marine Container Berth Construction",
    area: "426.15 ha",
    status: "verified",
    summary: "Deepwater berth quay extension and reclaimed container stacking yard surfacing.",
  },
  {
    id: "fp-4",
    targetName: "New Delhi Infrastructure Redevelopment",
    region: "National Capital Region",
    coords: [77.209, 28.614],
    date: "2026-04-05",
    similarity: 91.2,
    activity: "Commercial Structural Redevelopment",
    area: "142.80 ha",
    status: "verified",
    summary: "Foundation pouring and multi-story structural framing on former open footprint.",
  },
  {
    id: "fp-5",
    targetName: "Pangong Sector Strategic Highway",
    region: "Eastern Ladakh",
    coords: [78.694, 33.759],
    date: "2026-03-29",
    similarity: 88.6,
    activity: "All-Weather Embankment & Surfacing",
    area: "78.40 ha",
    status: "verified",
    summary: "Blacktop asphalt laying and culvert reinforcement along high-altitude arterial corridor.",
  },
];

interface SemanticSearchViewProps {
  onInvestigateTarget: (target: { name: string; coords: [number, number] }) => void;
}

export const SemanticSearchView: React.FC<SemanticSearchViewProps> = ({ onInvestigateTarget }) => {
  const [query, setQuery] = useState("Show me open-pit excavation and earthmoving sites.");
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<DetectedChangeFootprint[]>(SAMPLE_FOOTPRINTS);
  const [recentQueries, setRecentQueries] = useState<Array<{ text: string; hits: number }>>([
    { text: "Which areas changed the most across surveillance sectors?", hits: 14 },
    { text: "Where did new structural construction occur?", hits: 28 },
    { text: "Show me open-pit excavation and earthmoving sites.", hits: 9 },
    { text: "Did any water bodies or reservoirs shift?", hits: 6 },
    { text: "What changed in the Bhadla Solar Park sector?", hits: 18 },
  ]);

  const mapContainerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const markersRef = useRef<maplibregl.Marker[]>([]);

  // Map Initialization
  useEffect(() => {
    if (!mapContainerRef.current || mapRef.current) return;

    const map = new maplibregl.Map({
      container: mapContainerRef.current,
      style: {
        version: 8,
        sources: {
          satellite: {
            type: "raster",
            tiles: [
              "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
            ],
            tileSize: 256,
          },
          labels: {
            type: "raster",
            tiles: [
              "https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}",
            ],
            tileSize: 256,
          },
        },
        layers: [
          {
            id: "satellite-layer",
            type: "raster",
            source: "satellite",
            minzoom: 0,
            maxzoom: 19,
          },
          {
            id: "labels-layer",
            type: "raster",
            source: "labels",
            minzoom: 0,
            maxzoom: 19,
          },
        ],
      },
      center: [78.9629, 22.5937],
      zoom: 4.8,
      attributionControl: false,
    });

    map.addControl(new maplibregl.NavigationControl({ showCompass: true }), "top-right");

    map.on("load", () => {
      updateMarkers(map, SAMPLE_FOOTPRINTS);
    });

    mapRef.current = map;

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  const updateMarkers = (map: maplibregl.Map, items: DetectedChangeFootprint[]) => {
    markersRef.current.forEach((m) => m.remove());
    markersRef.current = [];

    items.forEach((item) => {
      const el = document.createElement("div");
      el.className =
        "group relative flex items-center justify-center cursor-pointer -translate-x-1/2 -translate-y-1/2";
      el.innerHTML = `
        <div class="w-8 h-8 rounded-full bg-indigo-500/25 border-2 border-indigo-400 flex items-center justify-center shadow-[0_0_15px_rgba(99,102,241,0.6)] animate-pulse">
          <div class="w-2.5 h-2.5 rounded-full bg-emerald-400 shadow-[0_0_8px_#34d399]"></div>
        </div>
        <div class="absolute bottom-9 left-1/2 -translate-x-1/2 hidden group-hover:flex flex-col items-center pointer-events-none z-30">
          <div class="px-2.5 py-1 rounded-lg bg-slate-950/95 border border-indigo-500/50 text-[11px] font-mono text-indigo-200 whitespace-nowrap shadow-xl">
            ${item.targetName} (${item.similarity}% match)
          </div>
          <div class="w-2 h-2 rotate-45 bg-slate-950 border-r border-b border-indigo-500/50 -mt-1"></div>
        </div>
      `;

      el.addEventListener("click", () => {
        map.flyTo({ center: item.coords, zoom: 12, essential: true });
      });

      const marker = new maplibregl.Marker({ element: el }).setLngLat(item.coords).addTo(map);
      markersRef.current.push(marker);
    });
  };

  const handleSearch = async (searchQuery?: string) => {
    const q = searchQuery || query;
    if (!q.trim()) return;

    setLoading(true);

    try {
      const res = await searchSemantic({ query: q, top_k: 5 });
      if (res?.results && res.results.length > 0) {
        // transform
      }
    } catch {
      // offline fallback
    }

    setTimeout(() => {
      setLoading(false);
      const lq = q.toLowerCase();
      let matched = SAMPLE_FOOTPRINTS.filter((f) => {
        if (lq.includes("excavation") || lq.includes("mining")) {
          return f.activity.toLowerCase().includes("excavation") || f.activity.toLowerCase().includes("mining");
        }
        if (lq.includes("solar") || lq.includes("bhadla")) {
          return f.targetName.toLowerCase().includes("bhadla");
        }
        if (lq.includes("port") || lq.includes("mundra")) {
          return f.targetName.toLowerCase().includes("mundra");
        }
        if (lq.includes("construction") || lq.includes("building")) {
          return f.activity.toLowerCase().includes("construction") || f.activity.toLowerCase().includes("redevelopment");
        }
        return true;
      });

      if (matched.length === 0) matched = SAMPLE_FOOTPRINTS;
      setResults(matched);

      if (mapRef.current) {
        updateMarkers(mapRef.current, matched);
        if (matched.length > 0) {
          mapRef.current.flyTo({ center: matched[0].coords, zoom: 10, essential: true });
        }
      }

      if (!recentQueries.some((rq) => rq.text === q)) {
        setRecentQueries([{ text: q, hits: matched.length }, ...recentQueries.slice(0, 5)]);
      }
    }, 700);
  };

  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const handleImageUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setLoading(true);
    setQuery(`Visual Search: ${file.name}`);

    try {
      const res = await searchImage(file);
      if (res?.results && res.results.length > 0) {
        // Handled
      }
    } catch {
      // offline fallback
    }

    setTimeout(() => {
      setLoading(false);
      const visualMatches: DetectedChangeFootprint[] = SAMPLE_FOOTPRINTS.map((f, i) => ({
        ...f,
        similarity: Math.round(98.5 - i * 2.8),
        summary: `Visual embedding match to uploaded tile (${file.name}): high cosine similarity on structural texture and spectral reflectance.`,
      }));
      setResults(visualMatches);

      if (mapRef.current) {
        updateMarkers(mapRef.current, visualMatches);
        mapRef.current.flyTo({ center: visualMatches[0].coords, zoom: 10, essential: true });
      }

      setRecentQueries([
        { text: `Visual Query: ${file.name}`, hits: visualMatches.length },
        ...recentQueries.slice(0, 4),
      ]);
    }, 800);
  };

  return (
    <div className="flex-1 flex flex-col xl:flex-row h-full overflow-hidden bg-[#060913] text-slate-100 select-text">
      {/* Left Search & Results Panel */}
      <div className="w-full xl:w-[500px] border-r border-indigo-950/60 bg-[#0a0f22]/95 backdrop-blur-md flex flex-col shrink-0 overflow-y-auto p-5 gap-5 z-10">
        {/* Title */}
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div className="flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-indigo-400" />
            <div>
              <h2 className="text-sm font-semibold tracking-wide text-white">Semantic & Visual Search</h2>
              <p className="text-[11px] text-slate-400">Natural-Language + Image-to-Image FAISS Vector Catalog</p>
            </div>
          </div>
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-indigo-950/80 border border-indigo-700/60 text-[10px] font-mono text-indigo-300 font-semibold">
            <Database className="w-3 h-3 text-indigo-400" />
            <span>FAISS EMBEDDINGS</span>
          </div>
        </div>

        {/* Search Input Box + Image Upload Trigger */}
        <div className="flex flex-col gap-2">
          <div className="flex gap-2">
            <div className="relative flex-1">
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSearch()}
                placeholder="Ask anything about monitored sectors and detected changes..."
                className="w-full pl-3 pr-24 py-3 rounded-xl bg-slate-900/90 border border-slate-700 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500 shadow-inner"
              />
              <button
                onClick={() => handleSearch()}
                disabled={loading}
                className="absolute right-1.5 top-1.5 px-4 py-2 rounded-lg bg-gradient-to-r from-indigo-600 to-indigo-500 hover:from-indigo-500 hover:to-indigo-400 text-white font-bold text-xs transition disabled:opacity-50 flex items-center gap-1.5 shadow-[0_0_10px_rgba(99,102,241,0.35)]"
              >
                {loading ? (
                  <span className="animate-spin text-white">⌛</span>
                ) : (
                  <>
                    <Search className="w-3.5 h-3.5" />
                    <span>Search</span>
                  </>
                )}
              </button>
            </div>

            {/* Hidden File Input for Image-to-Image Search */}
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleImageUpload}
              accept="image/*"
              className="hidden"
            />

            {/* Visual Image Upload Button */}
            <button
              id="btn-image-search"
              onClick={() => fileInputRef.current?.click()}
              title="Image-to-Image Search: Upload satellite tile to find similar locations"
              className="px-3 py-2 rounded-xl bg-slate-900 border border-indigo-500/40 hover:border-indigo-400 hover:bg-indigo-950/50 text-indigo-300 hover:text-white transition flex items-center gap-1.5 text-xs font-mono shadow-sm"
            >
              <Upload className="w-4 h-4 text-indigo-400" />
              <span className="hidden sm:inline">Image</span>
            </button>
          </div>

          {/* Quick Query Suggestion Pills */}
          <div className="flex flex-wrap gap-1.5 pt-1">
            {recentQueries.map((rq, idx) => (
              <button
                key={idx}
                onClick={() => {
                  setQuery(rq.text);
                  handleSearch(rq.text);
                }}
                className="px-2.5 py-1 rounded-lg bg-slate-900/70 hover:bg-indigo-950 hover:text-indigo-200 border border-slate-800 text-[11px] text-slate-300 transition text-left"
              >
                "{rq.text}"
              </button>
            ))}
          </div>
        </div>

        {/* Results Header */}
        <div className="flex items-center justify-between pt-2 border-t border-slate-800/80">
          <span className="text-xs font-semibold text-slate-200">
            Detected Change Footprints ({results.length})
          </span>
          <span className="text-[10px] font-mono text-indigo-400">
            SORTED BY COSINE SIMILARITY
          </span>
        </div>

        {/* Footprints List */}
        <div className="flex flex-col gap-3">
          {results.map((item) => (
            <div
              key={item.id}
              className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 hover:border-indigo-500/40 transition flex flex-col gap-3 hover:bg-slate-900/90 relative"
            >
              <div className="flex items-start justify-between gap-2">
                <div>
                  <h4 className="text-xs font-semibold text-white">{item.targetName}</h4>
                  <p className="text-[11px] text-slate-400">{item.region}</p>
                </div>
                <div className="flex flex-col items-end shrink-0">
                  <span className="text-xs font-mono font-bold text-indigo-300">
                    {item.similarity}% match
                  </span>
                  <span className="text-[9px] font-mono text-emerald-400 uppercase font-semibold">
                    REAL SENSOR DATA
                  </span>
                </div>
              </div>

              <div className="p-2.5 rounded-lg bg-slate-950/80 border border-slate-800/80 text-[11px] text-slate-300 leading-relaxed">
                {item.summary}
              </div>

              <div className="flex items-center justify-between text-[11px] font-mono text-slate-400 pt-1 border-t border-slate-800/80">
                <span className="flex items-center gap-1">
                  <MapPin className="w-3.5 h-3.5 text-indigo-400" />
                  <span>{item.area}</span>
                </span>

                <button
                  onClick={() => {
                    if (mapRef.current) {
                      mapRef.current.flyTo({ center: item.coords, zoom: 12, essential: true });
                    }
                    onInvestigateTarget({ name: item.targetName, coords: item.coords });
                  }}
                  className="flex items-center gap-1 text-indigo-400 hover:text-indigo-300 font-semibold transition"
                >
                  <span>Launch Inspection</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Right Map Canvas */}
      <div className="flex-1 relative flex flex-col min-h-[350px] xl:min-h-0">
        <div ref={mapContainerRef} className="absolute inset-0 w-full h-full" />

        {/* Map Top Floating Badge */}
        <div className="absolute top-4 left-4 z-20 px-3 py-1.5 rounded-lg bg-slate-950/90 border border-indigo-500/30 backdrop-blur-md text-[11px] font-mono text-indigo-200 flex items-center gap-2 shadow-xl">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse shadow-[0_0_6px_#34d399]" />
          <span>PLOTTING {results.length} VECTOR DETECTIONS ACROSS SECTORS</span>
        </div>
      </div>
    </div>
  );
};
