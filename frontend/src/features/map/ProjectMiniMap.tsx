import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/features/auth/AuthContext";
import { toast } from "@/lib/toast";
import { ageLabel, getMiniMap, setProjectLocation } from "@/features/attendance/api";
import { LeafletMap, type MapLine, type MapMarker } from "./LeafletMap";
import "@/features/attendance/attendance.css";

/**
 * Minimapa en la ficha de la obra: su pin, el técnico responsable en su última
 * ubicación conocida y la distancia en línea recta entre los dos. «Cómo llegar»
 * abre Google Maps con la ruta real (gratis, sin llave).
 */
export function ProjectMiniMap({ projectId }: { projectId: string }) {
  const qc = useQueryClient();
  const { hasPermission } = useAuth();
  const puedeUbicar = hasPermission("projects.update");
  const [ubicando, setUbicando] = useState(false);
  const { data } = useQuery({ queryKey: ["mini-map", projectId], queryFn: () => getMiniMap(projectId), refetchInterval: 60_000 });
  const fijar = useMutation({
    mutationFn: ({ lat, lng }: { lat: number; lng: number }) => setProjectLocation(projectId, lat, lng),
    onSuccess: () => { toast("Ubicación de la obra guardada"); setUbicando(false); qc.invalidateQueries({ queryKey: ["mini-map", projectId] }); },
  });

  const { markers, lines } = useMemo(() => {
    const ms: MapMarker[] = [];
    const ls: MapLine[] = [];
    if (data?.located && data.latitude != null && data.longitude != null) {
      ms.push({ id: "obra", lat: data.latitude, lng: data.longitude, kind: "project", tone: "brand",
        lines: [data.title, data.address] });
      const loc = data.technician?.location;
      if (loc) {
        ms.push({ id: "tec", lat: loc.latitude, lng: loc.longitude, kind: "person", tone: loc.fresh ? "ok" : "muted",
          badge: (data.technician?.user_name ?? "T").slice(0, 1).toUpperCase(),
          lines: [data.technician?.user_name ?? "Técnico", `${loc.fresh ? "Ubicación reciente" : "Última ubicación conocida"} · ${ageLabel(loc.age_minutes)}`] });
        ls.push({ id: "linea", from: [loc.latitude, loc.longitude], to: [data.latitude, data.longitude], dashed: true });
      }
    }
    return { markers: ms, lines: ls };
  }, [data]);

  if (!data) return null;
  return (
    <section className="annex-section" aria-labelledby="anexo-mapa">
      <div className="annex-section-head">
        <h3 id="anexo-mapa">Ubicación de la obra</h3>
        {data.directions_url && <a className="att-btn" href={data.directions_url} target="_blank" rel="noreferrer noopener">Cómo llegar</a>}
      </div>
      <p className="acta-lead">{data.address || "Sin dirección"}
        {data.technician && <> · Responsable: <strong>{data.technician.user_name}</strong>
          {data.straight_line_km != null && <> · a {data.straight_line_km} km en línea recta (estimado)</>}
          {data.technician.location == null && " · sin ubicación reciente"}</>}</p>
      {data.located || ubicando ? (
        <LeafletMap label={`Mapa de ${data.title}`} markers={markers} lines={lines} height={260}
          fit={!ubicando} onMapClick={ubicando ? (lat, lng) => fijar.mutate({ lat, lng }) : undefined} />
      ) : <p className="att-muted">La obra no tiene coordenadas.</p>}
      {puedeUbicar && (
        <p>{ubicando ? <>Toca el mapa donde está la obra. <button type="button" className="att-btn is-link"
          onClick={() => setUbicando(false)}>Cancelar</button></> : <button type="button" className="att-btn is-link"
          onClick={() => setUbicando(true)}>{data.located ? "Corregir la ubicación" : "Fijar en el mapa"}</button>}</p>
      )}
    </section>
  );
}
