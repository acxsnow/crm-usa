import { useCallback, useState } from "react";

export type GeoStatus = "idle" | "requesting" | "granted" | "denied";

/** Posición del teléfono para marcar visitas, fotos y firmas. Exige HTTPS
 * fuera de localhost; si el navegador la niega, se sigue sin GPS. */
export function useGeolocation() {
  const [coords, setCoords] = useState<{ latitude: number; longitude: number } | null>(null);
  const [status, setStatus] = useState<GeoStatus>("idle");

  const request = useCallback(() => {
    if (!navigator.geolocation) {
      setStatus("denied");
      return;
    }
    setStatus("requesting");
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setCoords({ latitude: pos.coords.latitude, longitude: pos.coords.longitude });
        setStatus("granted");
      },
      () => setStatus("denied"),
      { enableHighAccuracy: true, timeout: 10000 },
    );
  }, []);

  return { coords, status, request };
}
