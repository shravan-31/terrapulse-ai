# DESIGN — UI/UX & Motion System

## 1. Design intent

A professional geospatial intelligence dashboard: map first, dense but calm, dark theme.
Every animation must communicate **real state** (job progress, selection, comparison, data arrival). No decorative fake "AI scanning".

## 2. Layout

```
┌───────────────────────────────────────────────────────────────────────┐
│ Search satellite imagery...        [Search] [Image Search] [Change Analysis] │
├──────────────┬────────────────────────────────────────────────────────┤
│ Filters      │                         MAP                            │
│  AOI         │        Satellite + results + change + similar          │
│  Dates       │                                                        │
│  Sensor      │                                                        │
│  Cloud %     │                                                        │
│  Resolution  │                                                        │
│  Confidence  │                                                        │
│  Change type │                                                        │
├──────────────┴────────────────────────────────────────────────────────┤
│ Timeline (real observations only)  ▶ time-lapse                       │
├───────────────────────────────────────────────────────────────────────┤
│ Results | Before-After | Change Details | AI Assistant | Review Queue │
└───────────────────────────────────────────────────────────────────────┘
```
- Left panel collapsible; bottom dock resizable.
- Small screens: filters → drawer; dock → bottom sheet with drag-to-expand.

## 3. Visual language

| Token | Value (suggested) |
|-------|-------------------|
| Background | `#0B0F14` (app), `#121821` (panels), `#1A2230` (raised) |
| Border | `rgba(255,255,255,0.08)` 1px |
| Text | `#E6EDF5` primary, `#9AA7B8` secondary |
| Accent (selection) | `#38BDF8` |
| Confirmed | `#22C55E` |
| Candidate / uncertain | `#F59E0B` |
| Rejected / error | `#EF4444` |
| Info | `#60A5FA` |
| Similar sites | `#A78BFA` |
| Radius | 10px panels, 8px controls |
| Shadow | soft, low-spread; glass effect only on floating panels |

Typography: Inter (UI), JetBrains Mono (IDs, coordinates, dates). Icons: lucide-react.
Define as CSS variables + Tailwind theme extension.

## 4. Change-type color/symbol legend

| Type | Color | Symbol |
|------|-------|--------|
| Construction | `#F97316` | ▣ |
| Construction expansion | `#FB923C` | ▣+ |
| Road development | `#EAB308` | ═ |
| Clearance | `#A16207` | ▱ |
| Water variation | `#06B6D4` | ≈ |
| Vegetation/land-cover | `#84CC16` | ❦ |
| Unknown | `#94A3B8` | ? |

Never rely on color alone — always pair with symbol/label.

## 5. Key components

**SearchBar** — single input, three mode buttons, parsed-filter chips shown below after Groq parse (editable). Shows warning chip if Groq fallback used.
**FilterPanel** — AOI tools (rect/polygon/circle), date range, sensor, cloud slider, resolution, confidence slider, change-type multi-select.
**MapView** — MapLibre + MapTiler; layer control with opacity per layer; coordinate readout; scale bar.
**Timeline** — nodes at real acquisition dates; dim cloudy/low-quality; empty gaps remain empty; playhead; range handles.
**BeforeAfter** — swipe / side-by-side / opacity; labels (date, sensor) per side; change polygon overlay.
**ChangePanel** — ID, type, area (m²), system confidence (uncalibrated), earliest supported / confirmed (with "exact date unknown"), before/after dates, sensor, scene IDs, coordinates, quality flags, AI explanation, review buttons.
**ReviewQueue** — Pending/Confirmed/Rejected/Flagged tabs; notes; keyboard shortcuts (C/R/F).
**Assistant** — chat with suggested prompts; streaming answer; cites change IDs.
**PipelineStepper** — stages from SSE; cached stages labeled.

## 6. Date semantics in the UI (critical)

Three visually distinct markers with a persistent legend:
- ◇ **Earliest supported observation** (first evidence in data)
- ● **Confirmed observation** (persisted in later good imagery)
- ✕/— **Exact event date: unknown** (shown as text, never as a marker)

## 7. Motion system

### 7.1 Tokens (`motion/tokens.ts`)
```ts
export const dur = { fast: 0.15, base: 0.25, slow: 0.45, cinematic: 0.9 };
export const ease = { out: [0.16, 1, 0.3, 1], inOut: [0.65, 0, 0.35, 1] };
export const spring = {
  soft:   { type: "spring", stiffness: 180, damping: 22 },
  snappy: { type: "spring", stiffness: 320, damping: 28 },
};
```
Variants: `fadeIn`, `fadeUp`, `slideInRight`, `slideInBottom`, `scaleIn`, `staggerContainer` (stagger 60–120 ms).

### 7.2 Catalog

| Area | Animation | Trigger (real state) |
|------|-----------|----------------------|
| App shell | Staggered panel entrance | First load |
| Left panel | Animated width collapse; `map.resize()` on complete | Toggle |
| Dock tabs | Shared underline via `layoutId`; `AnimatePresence mode="wait"` cross-fade | Tab change |
| Result cards | Staggered enter; hover lift; tap 0.98 | Results arrive |
| Map fly | `flyTo/fitBounds` ~1200 ms | Search results / selection |
| Result tiles | Rank-ordered fill-opacity fade-in | Results arrive |
| Selected tile | Pulsing ripple (rAF, cancelled on unmount) | Selection |
| Change polygons | Draw-in (fill-opacity 0→0.45, line-width 0→2); hover via feature-state; selected = slow dashed "marching" outline | Analysis complete / hover / select |
| AOI | Rubber-band preview; single snap pulse on finish | Drawing |
| Layers | Opacity cross-fade | Toggle |
| Timeline | Node hover scale + tooltip; `layoutId` glow glides; range handles spring | Interaction |
| Time-lapse | Cross-fade raster layers through **real** observations; playhead moves | Play |
| Date markers | Earliest → confirmed → latest appear sequentially (stagger 120 ms) | Analysis complete |
| Before/After | Divider drag (motion value + clip-path); synced maps in side-by-side; label flip on pair change | Interaction |
| Pipeline | Progress ring on active stage; SVG check draws (`pathLength`); failed stage shakes once + shows error/suggestion; "cached" completes instantly | SSE events |
| Confidence gauge | Arc 0→value with count-up; caption "System confidence (uncalibrated)" | Panel open |
| Metrics | Number tween | Value change |
| Quality flags | Chips pop with stagger; color = good/warn/bad | Panel open |
| Review | Confirm: check draw + collapse out; Reject: X + slide out; Flag: amber pulse; optimistic with rollback animation on failure; queue reorders with `layout` | Decision |
| Assistant | Bubble slide-up; progressive token stream; typing indicator only while awaiting Groq | Chat |
| Charts | Animate on first mount only | Mount |
| Loading | Skeleton shimmer only while a request is pending | Request |
| Toasts | Slide + auto-dismiss | Job complete/fail |

### 7.3 Rules
- DOM: animate only `transform` and `opacity` (except deliberate `layout` transitions).
- Map animation is imperative (MapLibre paint transitions, rAF) — never per-frame React state.
- Use `LazyMotion` + `domAnimation` for bundle size; lazy-load heavy views.
- Cancel all rAF loops/listeners on unmount; cap concurrent animated map layers.
- Target 60 fps mid-range laptop.

## 8. Accessibility

- `prefers-reduced-motion` respected via `useReducedMotion()`: disable flyTo animation, autoplay time-lapse, pulses, marching dashes; use instant or opacity-only changes.
- Settings toggle "Reduce animations" (Zustand, persisted) overrides system default.
- Keyboard: all map tools, timeline, swipe divider (arrow keys), tabs, review actions.
- Visible focus rings; animated panels never trap focus.
- `aria-live="polite"` for job progress and toasts; color never sole indicator; contrast ≥ WCAG AA.

## 9. States

Every data view defines: **loading** (skeleton), **empty** (explains why, suggests action), **error** (structured `error` + `suggestion`, retry), **partial** (e.g., Groq fallback), **offline/upstream failure** (Copernicus/Groq/MapTiler down).

Example empty state: "No imagery for this AOI/date range. Try a wider date range or lower cloud threshold." (`NO_IMAGERY`)

## 10. Copy guidelines

- Say "system confidence" not "probability"; add tooltip explaining it is uncalibrated.
- Say "earliest supported observation", never "date of construction".
- Label test fixtures clearly ("TEST DATA").
- Show model/version in change details footer.

## 11. Frontend testing of design behavior

- Reduced-motion snapshot tests (no transforms/flyTo).
- Timeline renders gaps for missing observations.
- Date-semantics legend present whenever dates displayed.
- Error/empty states rendered for each API error code.
