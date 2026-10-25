/**
 * Autorización de tratamiento de datos personales (aviso al momento de la
 * captura). El texto lo sirve el servidor (`GET /privacy/consent-notice`) para
 * que la pantalla muestre exactamente lo que se guarda en la constancia:
 * la versión, el idioma y el cuerpo completo se guardan con la firma.
 *
 * Lo usan los cuatro puntos donde se capturan datos del cliente: alta y edición
 * de cliente, expediente de venta y firma pública.
 */
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/apiClient";

export interface ConsentNotice {
  version: string;
  language: string;
  title: string;
  label: string;
  body: string;
}

export function useConsentNotice() {
  return useQuery({
    queryKey: ["consent-notice"],
    queryFn: async () => (await apiClient.get<ConsentNotice>("/privacy/consent-notice")).data,
    staleTime: Infinity,
  });
}

/** El texto que el cliente lee, tal como queda guardado en la constancia. */
export function DataConsentNotice({ notice, className = "" }: { notice: ConsentNotice; className?: string }) {
  return (
    <div className={`ui-consent ${className}`.trim()}>
      <p className="ui-consent-title">{notice.title}</p>
      {notice.body.split("\n\n").map((parrafo, i) => <p key={i}>{parrafo}</p>)}
      <small>Versión {notice.version} · {notice.language === "es" ? "español" : "inglés"}</small>
    </div>
  );
}

/** La marca con la que queda constancia de que el cliente autorizó. */
export function ConsentCheckbox({ notice, checked, onChange }: {
  notice: ConsentNotice; checked: boolean; onChange: (valor: boolean) => void;
}) {
  return (
    <label className="ui-consent-check">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      <span>{notice.label}</span>
    </label>
  );
}
