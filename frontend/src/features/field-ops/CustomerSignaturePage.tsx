import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { getPublicSignatureDetails, submitPublicCustomerSignature } from "./api";
import { SignaturePad } from "./SignaturePad";

export function CustomerSignaturePage() {
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const [name, setName] = useState("");
  const [done, setDone] = useState(false);
  const details = useQuery({ queryKey: ["public-signature", token], queryFn: () => getPublicSignatureDetails(token), enabled: Boolean(token), retry: false });
  const submit = useMutation({ mutationFn: (signature: string) => submitPublicCustomerSignature(token, name.trim(), signature), onSuccess: () => setDone(true) });

  if (!token) return <div className="signature-public-page"><div className="signature-card"><h1>Enlace incompleto</h1><p>Este enlace de firma no es válido.</p></div></div>;
  if (details.isLoading) return <div className="signature-public-page"><div className="signature-card"><p>Cargando documento...</p></div></div>;
  if (details.isError) return <div className="signature-public-page"><div className="signature-card"><div className="public-brand"><span className="brand-mark">P</span> PAP<span className="brand-dot">.</span>CRM</div><h1>Enlace no disponible</h1><p>El enlace ya fue utilizado, expiró o fue revocado. Solicita al equipo un nuevo enlace de firma.</p></div></div>;
  if (done) return <div className="signature-public-page"><div className="signature-card success-card"><div className="success-check">✓</div><h1>Firma recibida</h1><p>Gracias, {name}. El equipo ya puede continuar con la gestión de tu instalación.</p><small>Puedes cerrar esta ventana.</small></div></div>;
  const info = details.data!;
  return <div className="signature-public-page"><div className="signature-card"><div className="public-brand"><span className="brand-mark">P</span> PAP<span className="brand-dot">.</span>CRM</div><p className="eyebrow">CONFIRMACIÓN DE SERVICIO</p><h1>Firma del cliente</h1><p className="signature-intro">Revisa y firma la constancia de tu proyecto <strong>{info.project_title}</strong>.</p><div className="signature-notice">✓ El instalador ya firmó este documento.<br /><span>Este enlace es privado y vence el {new Date(info.expires_at).toLocaleDateString("es-CO")}.</span></div><label className="signature-label">Nombre completo<input value={name} onChange={(e) => setName(e.target.value)} placeholder="Escribe tu nombre" /></label><p className="signature-label">Firma dentro del recuadro</p><SignaturePad disabled={!name.trim() || submit.isPending} onCapture={(signature) => submit.mutate(signature)} /><small className="signature-legal">Al confirmar, declaras que revisaste la información y aceptas la constancia del servicio.</small>{submit.isError && <p className="form-error">No se pudo registrar la firma. El enlace puede haber expirado.</p>}</div></div>;
}
