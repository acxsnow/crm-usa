import { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

/**
 * Mapa con Leaflet y mapas de OpenStreetMap: sin llave ni costo (spec, «Mapa y
 * rutas»). La dirección de los mapas es una variable de entorno para pasar a un
 * proveedor con garantía (MapTiler, Stadia) sin tocar código. La atribución de
 * OpenStreetMap es obligatoria y queda visible.
 *
 * Los textos de los globos se arman con nodos de texto, nunca con HTML: el
 * nombre de un cliente no puede inyectar nada.
 */
const TILE_URL = import.meta.env.VITE_MAP_TILE_URL ?? "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
const TILE_ATTRIBUTION = import.meta.env.VITE_MAP_TILE_ATTRIBUTION
  ?? '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>';
// Phoenix, mientras no haya nada que mostrar.
const DEFAULT_CENTER: [number, number] = [33.4484, -112.074];

export interface MapMarker {
  id: string;
  lat: number;
  lng: number;
  kind: "person" | "project" | "origin";
  /** Color del pin (obra por estado, persona reciente o vieja). */
  tone?: "ok" | "warn" | "muted" | "info" | "brand";
  /** Texto corto dentro del pin (iniciales o número de parada). */
  badge?: string;
  /** Líneas del globo; la primera va en negrita. */
  lines: string[];
  link?: { href: string; label: string };
}

export interface MapLine {
  id: string;
  from: [number, number];
  to: [number, number];
  dashed?: boolean;
}

function popup(m: MapMarker): HTMLElement {
  const div = document.createElement("div");
  div.className = "map-popup";
  m.lines.forEach((t, i) => {
    const p = document.createElement(i === 0 ? "strong" : "span");
    p.textContent = t;
    div.appendChild(p);
  });
  if (m.link) {
    const a = document.createElement("a");
    a.href = m.link.href;
    a.textContent = m.link.label;
    div.appendChild(a);
  }
  return div;
}

function icon(m: MapMarker): L.DivIcon {
  const el = document.createElement("span");
  el.className = `map-pin is-${m.kind} tone-${m.tone ?? "info"}`;
  el.textContent = m.badge ?? "";
  return L.divIcon({ html: el, className: "map-pin-wrap", iconSize: [30, 30], iconAnchor: [15, m.kind === "project" ? 30 : 15] });
}

export function LeafletMap({ markers, lines = [], height = 480, onMapClick, label, fit = true }: {
  markers: MapMarker[];
  lines?: MapLine[];
  height?: number | string;
  onMapClick?: (lat: number, lng: number) => void;
  label: string;
  fit?: boolean;
}) {
  const caja = useRef<HTMLDivElement>(null);
  const mapa = useRef<L.Map | null>(null);
  const capa = useRef<L.LayerGroup | null>(null);
  const clic = useRef(onMapClick);
  clic.current = onMapClick;

  useEffect(() => {
    if (!caja.current || mapa.current) return;
    const m = L.map(caja.current, { center: DEFAULT_CENTER, zoom: 10, scrollWheelZoom: false });
    L.tileLayer(TILE_URL, { attribution: TILE_ATTRIBUTION, maxZoom: 19 }).addTo(m);
    capa.current = L.layerGroup().addTo(m);
    m.on("click", (e: L.LeafletMouseEvent) => clic.current?.(e.latlng.lat, e.latlng.lng));
    mapa.current = m;
    return () => { m.remove(); mapa.current = null; };
  }, []);

  useEffect(() => {
    const m = mapa.current;
    const g = capa.current;
    if (!m || !g) return;
    g.clearLayers();
    for (const l of lines) {
      L.polyline([l.from, l.to], { color: "#2563eb", weight: 3, opacity: 0.7, dashArray: l.dashed ? "6 6" : undefined })
        .addTo(g);
    }
    for (const mk of markers) {
      L.marker([mk.lat, mk.lng], { icon: icon(mk), title: mk.lines[0], alt: mk.lines[0] })
        .bindPopup(popup(mk)).addTo(g);
    }
    if (fit && markers.length) {
      const b = L.latLngBounds(markers.map((x) => [x.lat, x.lng] as [number, number]));
      m.fitBounds(b, { padding: [36, 36], maxZoom: 15 });
    }
  }, [markers, lines, fit]);

  return <div ref={caja} className="map-box" style={{ height }} role="region" aria-label={label} />;
}
