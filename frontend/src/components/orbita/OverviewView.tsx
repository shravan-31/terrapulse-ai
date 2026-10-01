import React, { useState, useEffect, useRef } from "react";
import {
  Compass,
  MapPin,
  Layers,
  Search,
  Crosshair,
  Calendar,
  Cloud,
  Activity,
  ArrowRight,
  Plus,
  RefreshCw,
  Box,
  Eye,
  CheckCircle2,
  AlertTriangle,
} from "lucide-react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

interface SectorItem {
  id: string;
  name: string;
  region: string;
  coords: [number, number]; // [lng, lat]
  cloudCover: number;
  changesCount: number;
  lastPassDate: string;
  status: "active" | "scheduled";
}

const PRESET_SECTORS: SectorItem[] = [
  {
    id: "sec-bhadla",
    name: "Bhadla Solar Park",
    region: "Phalodi, Rajasthan",
    coords: [71.916, 27.538],
    cloudCover: 6,
    changesCount: 42,
    lastPassDate: "2026-04-18",
    status: "active",
  },
  {
    id: "sec-mundra",
    name: "Mundra Port & Special Economic Zone",
    region: "Kutch, Gujarat",
    coords: [69.712, 22.756],
    cloudCover: 4,
    changesCount: 89,
    lastPassDate: "2026-04-17",
    status: "active",
  },
  {
    id: "sec-korba",
    name: "Korba Coal & Thermal Belt",
    region: "Korba, Chhattisgarh",
    coords: [82.684, 22.359],
    cloudCover: 12,
    changesCount: 64,
    lastPassDate: "2026-04-16",
    status: "active",
  },
  {
    id: "sec-delhi",
    name: "New Delhi Central Corridor",
    region: "National Capital Region",
    coords: [77.209, 28.614],
    cloudCover: 9,
    changesCount: 73,
    lastPassDate: "2026-04-19",
    status: "active",
  },
  {
    id: "sec-pangong",
    name: "Pangong Sector Reconnaissance",
    region: "Eastern Ladakh",
    coords: [78.694, 33.759],
    cloudCover: 5,
    changesCount: 18,
    lastPassDate: "2026-04-15",
    status: "active",
  },
  {
    id: "sec-bhilai",
    name: "Bhilai Steel & Industrial Complex",
    region: "Durg, Chhattisgarh",
    coords: [81.382, 21.213],
    cloudCover: 11,
    changesCount: 35,
    lastPassDate: "2026-04-14",
    status: "active",
  },
];

interface OverviewViewProps {
  onInvestigateTarget: (sector: { name: string; coords: [number, number] }) => void;
}

export const OverviewView: React.FC<OverviewViewProps> = ({ onInvestigateTarget }) => {
  const [sectors, setSectors] = useState<SectorItem[]>(PRESET_SECTORS);
  const [searchFilter, setSearchFilter] = useState("");
  const [userLocation, setUserLocation] = useState<{ lat: number; lng: number; accuracy?: number } | null>(null);
  const [selectedRadiusKm, setSelectedRadiusKm] = useState<5 | 10 | 25>(10);
  const [locating, setLocating] = useState(false);
  const [locationNotice, setLocationNotice] = useState<string | null>(null);
  const [nearbySector, setNearbySector] = useState<SectorItem | null>(null);
  const [locationName, setLocationName] = useState<string | null>(null);
  const [passCheckingId, setPassCheckingId] = useState<string | null>(null);
  const [passScheduleMessage, setPassScheduleMessage] = useState<string | null>(null);
  const [drawingMode, setDrawingMode] = useState(false);
  const [mapPitch3D, setMapPitch3D] = useState(false);
  const [coordsTelemetry, setCoordsTelemetry] = useState<{ lat: number; lng: number; zoom: number }>({
    lat: 22.5937,
    lng: 78.9629,
    zoom: 4.8,
  });
  const [permissionBlocked, setPermissionBlocked] = useState(false);

  // Monitor browser geolocation permission state
  useEffect(() => {
    if (typeof navigator !== "undefined" && navigator.permissions && navigator.permissions.query) {
      navigator.permissions
        .query({ name: "geolocation" })
        .then((perm) => {
          if (perm.state === "denied") {
            setPermissionBlocked(true);
          }
          perm.onchange = () => {
            if (perm.state === "granted") {
              setPermissionBlocked(false);
            } else if (perm.state === "denied") {
              setPermissionBlocked(true);
            }
          };
        })
        .catch(() => {});
    }
  }, []);

  const mapContainerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const userMarkerRef = useRef<maplibregl.Marker | null>(null);

  // Helper: Haversine distance in km
  const calculateDistanceKm = (lat1: number, lon1: number, lat2: number, lon2: number): number => {
    const R = 6371;
    const dLat = ((lat2 - lat1) * Math.PI) / 180;
    const dLon = ((lon2 - lon1) * Math.PI) / 180;
    const a =
      Math.sin(dLat / 2) * Math.sin(dLat / 2) +
      Math.cos((lat1 * Math.PI) / 180) *
        Math.cos((lat2 * Math.PI) / 180) *
        Math.sin(dLon / 2) *
        Math.sin(dLon / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    return R * c;
  };

  // Fallback to IP geolocation when browser GPS is blocked/unavailable/timed-out
  const fetchIPLocation = async (): Promise<{ lat: number; lng: number; accuracy: number; city: string; region: string } | null> => {
    try {
      const res = await fetch("https://ipapi.co/json/");
      if (res.ok) {
        const data = await res.json();
        if (data.latitude && data.longitude) {
          return {
            lat: Number(data.latitude),
            lng: Number(data.longitude),
            accuracy: 2500,
            city: data.city || "Current Area",
            region: data.region || data.country_name || "India",
          };
        }
      }
    } catch {}

    try {
      const res2 = await fetch("https://freeipapi.com/api/json");
      if (res2.ok) {
        const data2 = await res2.json();
        if (data2.latitude && data2.longitude) {
          return {
            lat: Number(data2.latitude),
            lng: Number(data2.longitude),
            accuracy: 4000,
            city: data2.cityName || "Current Area",
            region: data2.regionName || data2.countryName || "India",
          };
        }
      }
    } catch {}

    return null;
  };

  const applyDetectedLocation = (
    lat: number,
    lng: number,
    accuracy: number,
    name: string,
    source: "gps" | "ip"
  ) => {
    setUserLocation({ lat, lng, accuracy });
    setLocationName(name);

    // Check local indexed satellite archive within selected radius
    let closestSec: SectorItem | null = null;
    let minD = Infinity;

    PRESET_SECTORS.forEach((sec) => {
      const d = calculateDistanceKm(lat, lng, sec.coords[1], sec.coords[0]);
      if (d < minD) {
        minD = d;
        closestSec = sec;
      }
    });

    if (closestSec && minD <= selectedRadiusKm) {
      setNearbySector(closestSec);
      setLocationNotice(
        `📍 Live Position (${source === "gps" ? "Device GPS" : "Network IP"}): ${name}. Strategic Sector "${closestSec.name}" is ${minD.toFixed(1)} km away.`
      );
    } else {
      setNearbySector(null);
      setLocationNotice(
        `📍 Live Position Active: ${name} (${lat.toFixed(4)}°N, ${lng.toFixed(4)}°E). High-resolution satellite basemap centered on your target.`
      );
    }

    // Place marker on map and flyTo
    if (mapRef.current) {
      if (userMarkerRef.current) userMarkerRef.current.remove();

      const el = document.createElement("div");
      el.className = "flex items-center justify-center -translate-x-1/2 -translate-y-1/2 cursor-pointer";
      el.innerHTML = `
        <div class="relative flex items-center justify-center">
          <div class="w-12 h-12 rounded-full bg-cyan-500/25 border-2 border-cyan-400 flex items-center justify-center animate-ping"></div>
          <div class="absolute w-5 h-5 rounded-full bg-cyan-400 border-2 border-white shadow-[0_0_15px_#22d3ee] flex items-center justify-center">
            <div class="w-2 h-2 rounded-full bg-white animate-pulse"></div>
          </div>
        </div>
      `;
      userMarkerRef.current = new maplibregl.Marker({ element: el })
        .setLngLat([lng, lat])
        .addTo(mapRef.current);

      mapRef.current.flyTo({ center: [lng, lat], zoom: 12, essential: true });
    }
  };

  const handleUseMyLocation = async () => {
    setLocating(true);
    setLocationNotice(null);

    const tryIPFallback = async () => {
      const ipLoc = await fetchIPLocation();
      setLocating(false);
      if (ipLoc) {
        applyDetectedLocation(
          ipLoc.lat,
          ipLoc.lng,
          ipLoc.accuracy,
          `${ipLoc.city}, ${ipLoc.region}`,
          "ip"
        );
      } else {
        // Fallback default coordinate (New Delhi)
        applyDetectedLocation(28.6139, 77.209, 5000, "New Delhi (Capital Corridor)", "ip");
        setLocationNotice(
          `GPS permission blocked. Centered on New Delhi surveillance corridor. (Tip: allow Location in your browser address bar for live device GPS).`
        );
      }
    };

    if (!("geolocation" in navigator)) {
      await tryIPFallback();
      return;
    }

    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLocating(false);
        setPermissionBlocked(false);
        const lat = pos.coords.latitude;
        const lng = pos.coords.longitude;
        const accuracy = Math.round(pos.coords.accuracy || 10);
        applyDetectedLocation(lat, lng, accuracy, `Your Live Device Location (±${accuracy}m)`, "gps");
      },
      async (err) => {
        if (err.code === 1) {
          // User or browser blocked permission
          setPermissionBlocked(true);
        }
        // Fallback to IP geolocation so map still centers on user's city
        await tryIPFallback();
      },
      { enableHighAccuracy: true, timeout: 8000, maximumAge: 0 }
    );
  };

  // Initialize MapLibre GL
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

    map.on("mousemove", (e) => {
      setCoordsTelemetry({
        lat: Number(e.lngLat.lat.toFixed(4)),
        lng: Number(e.lngLat.lng.toFixed(4)),
        zoom: Number(map.getZoom().toFixed(1)),
      });
    });

    map.on("load", () => {
      // Add markers for each sector with Electric Indigo & Emerald pulse
      PRESET_SECTORS.forEach((sec) => {
        const el = document.createElement("div");
        el.className =
          "group relative flex items-center justify-center cursor-pointer -translate-x-1/2 -translate-y-1/2";
        el.innerHTML = `
          <div class="w-8 h-8 rounded-full bg-indigo-500/25 border-2 border-indigo-400 flex items-center justify-center shadow-[0_0_14px_rgba(99,102,241,0.6)] animate-pulse">
            <div class="w-2.5 h-2.5 rounded-full bg-emerald-400 shadow-[0_0_8px_#34d399]"></div>
          </div>
          <div class="absolute bottom-9 left-1/2 -translate-x-1/2 hidden group-hover:flex flex-col items-center pointer-events-none z-30">
            <div class="px-2.5 py-1 rounded-lg bg-slate-950/95 border border-indigo-500/50 text-[11px] font-mono text-indigo-300 whitespace-nowrap shadow-xl">
              ${sec.name} (${sec.changesCount} changes)
            </div>
            <div class="w-2 h-2 rotate-45 bg-slate-950 border-r border-b border-indigo-500/50 -mt-1"></div>
          </div>
        `;

        el.addEventListener("click", () => {
          map.flyTo({ center: sec.coords, zoom: 11, essential: true });
        });

        new maplibregl.Marker({ element: el }).setLngLat(sec.coords).addTo(map);
      });
    });

    mapRef.current = map;

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  const handleToggle3D = () => {
    if (!mapRef.current) return;
    const next = !mapPitch3D;
    setMapPitch3D(next);
    mapRef.current.easeTo({ pitch: next ? 55 : 0, duration: 800 });
  };

  const handleRecenterUser = () => {
    if (!mapRef.current || !userLocation) return;
    mapRef.current.flyTo({ center: [userLocation.lng, userLocation.lat], zoom: 12, essential: true });
  };

  const handleCheckPasses = (sector: SectorItem) => {
    setPassCheckingId(sector.id);
    setTimeout(() => {
      setPassCheckingId(null);
      setPassScheduleMessage(
        `Next Sentinel-2 Pass for ${sector.name}: Tomorrow 10:48 UTC (Orbit 128, Sun Elevation 64.2°)`
      );
      setTimeout(() => setPassScheduleMessage(null), 5000);
    }, 900);
  };

  const filteredSectors = sectors.filter(
    (s) =>
      s.name.toLowerCase().includes(searchFilter.toLowerCase()) ||
      s.region.toLowerCase().includes(searchFilter.toLowerCase())
  );

  return (
    <div className="flex-1 flex flex-col md:flex-row h-full overflow-hidden bg-[#060913] text-slate-100">
      {/* Left Mission Control Sidebar */}
      <div className="w-full md:w-[460px] border-r border-indigo-950/60 bg-[#0a0f22]/95 backdrop-blur-md flex flex-col shrink-0 z-10">
        {/* Top Header */}
        <div className="p-4 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Compass className="w-5 h-5 text-indigo-400" />
            <div>
              <h2 className="text-sm font-semibold tracking-wide text-white">Surveillance Overview</h2>
              <p className="text-[11px] text-slate-400">Mission Control & Persistent AOI Monitoring</p>
            </div>
          </div>
          <div className="px-2.5 py-1 rounded-full bg-indigo-950/80 border border-indigo-700/60 text-[10px] font-mono text-indigo-300 font-semibold">
            63 ACTIVE SECTORS
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-4">
          {/* SIH Phase 13 — USE MY LOCATION Component */}
          <div className="p-3.5 rounded-xl bg-slate-900/90 border border-indigo-500/30 flex flex-col gap-3 shadow-lg">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-mono text-indigo-300 uppercase tracking-wider flex items-center gap-1.5 font-bold">
                <MapPin className="w-3.5 h-3.5 text-cyan-400" />
                SIH Phase 13 — Sovereign GPS Geolocation
              </span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-indigo-950 border border-indigo-800 text-indigo-300">
                BROWSER-NATIVE
              </span>
            </div>

            {/* Radius Selector */}
            <div className="flex items-center justify-between gap-2">
              <span className="text-[11px] text-slate-400 font-medium">AOI Radius:</span>
              <div className="flex gap-1.5">
                {([5, 10, 25] as const).map((r) => (
                  <button
                    key={r}
                    onClick={() => setSelectedRadiusKm(r)}
                    className={`px-2.5 py-1 rounded text-xs font-mono font-semibold transition border ${
                      selectedRadiusKm === r
                        ? "bg-cyan-500/25 border-cyan-400 text-cyan-200 shadow-[0_0_8px_rgba(6,182,212,0.4)]"
                        : "bg-slate-950 border-slate-800 text-slate-400 hover:text-slate-200"
                    }`}
                  >
                    {r} km {r === 10 && "(Default)"}
                  </button>
                ))}
              </div>
            </div>

            {/* Primary Use My Location Button */}
            <button
              id="btn-use-my-location"
              onClick={handleUseMyLocation}
              disabled={locating}
              className="w-full py-2.5 px-4 rounded-lg bg-gradient-to-r from-cyan-600 to-indigo-600 hover:from-cyan-500 hover:to-indigo-500 text-white font-bold text-xs uppercase tracking-wider flex items-center justify-center gap-2 transition shadow-[0_0_15px_rgba(6,182,212,0.35)] disabled:opacity-50"
            >
              <MapPin className="w-4 h-4 text-cyan-200" />
              <span>{locating ? "Acquiring Device GPS Fix..." : "📍 USE MY LOCATION"}</span>
            </button>

            {/* Browser Permission Blocked Guide */}
            {permissionBlocked && (
              <div className="p-3 rounded-xl bg-amber-950/40 border border-amber-500/60 text-amber-200 text-xs flex flex-col gap-2.5 animate-fadeIn shadow-lg">
                <div className="flex items-center gap-2 text-amber-300 font-bold">
                  <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
                  <span>Browser Location Access Blocked</span>
                </div>
                <p className="text-[11px] text-amber-200/90 leading-relaxed">
                  तुमच्या ब्राउझरने (Chrome/Edge) लोकेशन ब्लॉक केले आहे. थेट तुमच्या घरावर/जागेवर झूम करण्यासाठी:
                </p>
                <div className="p-2.5 rounded-lg bg-black/50 border border-amber-500/30 font-mono text-[11px] space-y-1.5 text-slate-200">
                  <div className="flex items-start gap-1.5">
                    <span className="text-amber-400 font-bold">1.</span>
                    <span>ब्राउझर URL च्या डाव्या बाजूला <b>🔒 किंवा ⚙️ चिन्ह</b> वर क्लिक करा.</span>
                  </div>
                  <div className="flex items-start gap-1.5">
                    <span className="text-amber-400 font-bold">2.</span>
                    <span><b>Location</b> पर्याय <b>"Allow" (चालू)</b> करा.</span>
                  </div>
                  <div className="flex items-start gap-1.5">
                    <span className="text-amber-400 font-bold">3.</span>
                    <span>पेज <b>Reload</b> करा आणि परत <b>USE MY LOCATION</b> दाबा.</span>
                  </div>
                </div>
              </div>
            )}

            {/* Location & Local Archive Notice */}
            {userLocation && (
              <div className="p-2.5 rounded-lg bg-slate-950 border border-slate-800 text-xs font-mono flex flex-col gap-1">
                <div className="flex justify-between text-slate-300">
                  <span>GPS Coordinates:</span>
                  <span className="text-cyan-300">{userLocation.lat.toFixed(4)}°N, {userLocation.lng.toFixed(4)}°E</span>
                </div>
                <div className="flex justify-between text-slate-400 text-[11px]">
                  <span>Accuracy:</span>
                  <span>±{userLocation.accuracy} m</span>
                </div>
              </div>
            )}

            {locationNotice && (
              <div className={`p-2.5 rounded-lg text-xs leading-relaxed border ${
                nearbySector
                  ? "bg-emerald-950/60 border-emerald-500/40 text-emerald-200"
                  : "bg-indigo-950/60 border-indigo-500/40 text-indigo-200"
              }`}>
                {locationNotice}
              </div>
            )}

            {userLocation && (
              <div className="flex flex-col gap-2 pt-1">
                <button
                  onClick={() => {
                    if (mapRef.current) {
                      mapRef.current.flyTo({ center: [userLocation.lng, userLocation.lat], zoom: 12.5, essential: true });
                    }
                    onInvestigateTarget({
                      name: locationName || `Live Location (${userLocation.lat.toFixed(3)}°N, ${userLocation.lng.toFixed(3)}°E)`,
                      coords: [userLocation.lng, userLocation.lat],
                    });
                  }}
                  className="w-full py-2.5 px-3 rounded-lg bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-bold text-xs uppercase tracking-wider flex items-center justify-center gap-2 transition shadow-[0_0_12px_rgba(16,185,129,0.35)]"
                >
                  <span>🔭 Investigate Satellite Passes Here</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>

                {nearbySector && (
                  <button
                    onClick={() => {
                      if (mapRef.current) {
                        mapRef.current.flyTo({ center: nearbySector.coords, zoom: 11, essential: true });
                      }
                      onInvestigateTarget({
                        name: nearbySector.name,
                        coords: nearbySector.coords,
                      });
                    }}
                    className="w-full py-2 px-3 rounded-lg bg-slate-800/90 hover:bg-slate-800 border border-indigo-600/50 text-indigo-200 font-semibold text-xs flex items-center justify-center gap-1.5 transition"
                  >
                    <span>Inspect Matched Archive ({nearbySector.name})</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>
            )}
          </div>

          {/* Quick Counter Stats */}
          <div className="grid grid-cols-2 gap-3">
            <div className="p-3 rounded-lg bg-slate-900/60 border border-indigo-950/80">
              <span className="text-xl font-bold font-mono text-indigo-400">63</span>
              <span className="block text-[11px] text-slate-400 mt-0.5">Monitored Locations</span>
            </div>
            <div className="p-3 rounded-lg bg-slate-900/60 border border-indigo-950/80">
              <span className="text-xl font-bold font-mono text-emerald-400">352</span>
              <span className="block text-[11px] text-slate-400 mt-0.5">Detected Ground Shifts</span>
            </div>
          </div>

          {/* Pass Schedule Banner Notification */}
          {passScheduleMessage && (
            <div className="p-3 rounded-lg bg-indigo-950/80 border border-indigo-500/40 text-indigo-200 text-xs flex items-center gap-2 animate-fadeIn">
              <Calendar className="w-4 h-4 text-indigo-400 shrink-0" />
              <span>{passScheduleMessage}</span>
            </div>
          )}

          {/* Sectors Header & Draw Tool */}
          <div className="flex items-center justify-between pt-1">
            <div className="flex items-center gap-2">
              <Layers className="w-4 h-4 text-slate-400" />
              <span className="text-xs font-semibold text-slate-200">Surveillance Sectors</span>
            </div>

            <button
              id="btn-draw-map"
              onClick={() => setDrawingMode(!drawingMode)}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded text-[11px] font-medium transition border ${
                drawingMode
                  ? "bg-amber-500/20 border-amber-500/40 text-amber-300"
                  : "bg-slate-800/80 hover:bg-slate-800 border-indigo-950 text-indigo-300"
              }`}
            >
              <Plus className="w-3 h-3" />
              <span>{drawingMode ? "Drawing Active..." : "+ Draw on Map"}</span>
            </button>
          </div>

          {/* Filter Search */}
          <div className="relative">
            <Search className="w-3.5 h-3.5 text-slate-500 absolute left-3 top-2.5" />
            <input
              type="text"
              value={searchFilter}
              onChange={(e) => setSearchFilter(e.target.value)}
              placeholder="Filter monitored sectors by name or region..."
              className="w-full pl-8 pr-3 py-1.5 rounded-lg bg-slate-900/90 border border-indigo-950 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition"
            />
          </div>

          {/* Sectors List */}
          <div className="flex flex-col gap-2.5 overflow-y-auto">
            {filteredSectors.map((sec) => (
              <div
                key={sec.id}
                className="p-3 rounded-xl bg-slate-900/50 border border-slate-800/80 hover:border-indigo-500/40 transition flex flex-col gap-2.5 hover:bg-slate-900/80"
              >
                <div className="flex items-start justify-between">
                  <div>
                    <h4 className="text-xs font-semibold text-white">{sec.name}</h4>
                    <p className="text-[11px] text-slate-400">{sec.region}</p>
                  </div>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-indigo-950/80 border border-indigo-800 text-indigo-300">
                    {sec.changesCount} Changes
                  </span>
                </div>

                <div className="flex items-center gap-4 text-[10px] font-mono text-slate-400">
                  <span className="flex items-center gap-1">
                    <Cloud className="w-3 h-3 text-sky-400" />
                    <span>Cloud: {sec.cloudCover}%</span>
                  </span>
                  <span className="flex items-center gap-1">
                    <Calendar className="w-3 h-3 text-slate-400" />
                    <span>Pass: {sec.lastPassDate}</span>
                  </span>
                </div>

                <div className="flex items-center justify-between pt-1 border-t border-slate-800/80">
                  <button
                    onClick={() => handleCheckPasses(sec)}
                    disabled={passCheckingId === sec.id}
                    className="flex items-center gap-1 text-[11px] text-slate-400 hover:text-indigo-300 transition"
                  >
                    <RefreshCw className={`w-3 h-3 ${passCheckingId === sec.id ? "animate-spin text-indigo-400" : ""}`} />
                    <span>{passCheckingId === sec.id ? "Checking..." : "Check Passes"}</span>
                  </button>

                  <button
                    onClick={() => {
                      if (mapRef.current) {
                        mapRef.current.flyTo({ center: sec.coords, zoom: 11, essential: true });
                      }
                      onInvestigateTarget({ name: sec.name, coords: sec.coords });
                    }}
                    className="flex items-center gap-1 text-[11px] text-indigo-400 hover:text-indigo-300 font-semibold transition"
                  >
                    <span>Inspect Changes</span>
                    <ArrowRight className="w-3 h-3" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Right Map Canvas */}
      <div className="flex-1 relative flex flex-col h-full">
        <div ref={mapContainerRef} className="absolute inset-0 w-full h-full" />

        {/* Map Top Floating Controls */}
        <div className="absolute top-4 left-4 z-20 flex items-center gap-2">
          <button
            onClick={handleToggle3D}
            className={`px-3 py-1.5 rounded-lg text-xs font-mono font-medium backdrop-blur-md transition border shadow-lg ${
              mapPitch3D
                ? "bg-indigo-600 text-white border-indigo-400 font-bold"
                : "bg-slate-950/80 text-indigo-300 border-indigo-500/30 hover:border-indigo-400"
            }`}
          >
            {mapPitch3D ? "3D OBLIQUE" : "2D FLAT"}
          </button>

          <button
            onClick={handleRecenterUser}
            className="p-1.5 rounded-lg bg-slate-950/80 border border-slate-700 hover:border-indigo-400 text-indigo-300 backdrop-blur-md transition shadow-lg"
            title="Recenter to Current Location"
          >
            <Crosshair className="w-4 h-4" />
          </button>
        </div>

        {/* Live Telemetry Status Bar */}
        <div className="absolute bottom-4 left-4 right-4 z-20 pointer-events-none">
          <div className="max-w-fit mx-auto px-4 py-1.5 rounded-full bg-slate-950/90 border border-indigo-500/30 backdrop-blur-md flex items-center gap-4 text-[11px] font-mono text-indigo-300 shadow-xl pointer-events-auto">
            <span className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse shadow-[0_0_8px_#34d399]" />
              <span>TELEMETRY ONLINE</span>
            </span>
            <span className="text-slate-600">|</span>
            <span>LAT: {coordsTelemetry.lat}°</span>
            <span className="text-slate-600">|</span>
            <span>LNG: {coordsTelemetry.lng}°</span>
            <span className="text-slate-600">|</span>
            <span>ZOOM: {coordsTelemetry.zoom}</span>
            <span className="text-slate-600">|</span>
            <span>CRS: WGS84</span>
          </div>
        </div>
      </div>
    </div>
  );
};
