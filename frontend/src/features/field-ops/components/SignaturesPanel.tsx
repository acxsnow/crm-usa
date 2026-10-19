import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  fetchAttestationPdfObjectUrl,
  getAttestation,
  requestCustomerSignature,
  signAsCustomer,
  signAsTechnician,
} from "@/features/field-ops/api";
import { apiErrorMessage } from "@/features/field-ops/module5Api";
import { SignaturePad } from "@/features/field-ops/SignaturePad";
import { CheckCircleIcon, ClockIcon, SendIcon } from "./icons";

export const attestationKey = (projectId: string) => ["project-attestation", projectId] as const;

const cuando = (iso: string) =>
  new Date(iso).toLocaleString("es-CO", { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });

/**
 * Paso «Firmas del acta» (spec 2026-10-18-firmas-del-acta). El técnico firma
 * en pantalla. El cliente firma por un enlace a su correo o, si no tiene
 * correo ni internet, aquí mismo en el celular del técnico. Sin sockets: el
 * botón «Consultar si ya firmó» vuelve a pedir el acta.
 */
export function SignaturesPanel({ projectId, canSign }: { projectId: string; canSign: boolean }) {
  const qc = useQueryClient();
  const { data: acta, refetch, isFetching } = useQuery({
    queryKey: attestationKey(projectId), queryFn: () => getAttestation(projectId),
  });
  const [error, setError] = useState<string | null>(null);
  const [enPersona, setEnPersona] = useState(false);
  const [nombre, setNombre] = useState("");
  const [consulta, setConsulta] = useState<string | null>(null);
  const listo = (a: unknown) => { setError(null); qc.setQueryData(attestationKey(projectId), a); return qc.invalidateQueries({ queryKey: attestationKey(projectId) }); };

  const firmaTecnico = useMutation({
    mutationFn: (firma: string) => signAsTechnician(projectId, firma),
    onSuccess: listo, onError: (e) => setError(apiErrorMessage(e)),
    meta: { successMessage: "Firma del técnico guardada." },
  });
  const firmaCliente = useMutation({
    mutationFn: (firma: string) => signAsCustomer(projectId, nombre.trim(), firma),
    onSuccess: (a) => { setEnPersona(false); return listo(a); },
    onError: (e) => setError(apiErrorMessage(e)),
    meta: { successMessage: "Firma del cliente guardada." },
  });
  const enlace = useMutation({
    mutationFn: () => requestCustomerSignature(projectId),
    onSuccess: () => { setError(null); setConsulta(null); return qc.invalidateQueries({ queryKey: attestationKey(projectId) }); },
    onError: (e) => setError(apiErrorMessage(e, "No se pudo enviar el enlace. Verifica que el cliente tenga correo.")),
    meta: { successMessage: "Enlace de firma enviado al correo del cliente." },
  });

  const consultar = async () => {
    const { data } = await refetch();
    setConsulta(data?.customer_signed_at ? null : `Todavía no ha firmado (consultado a las ${new Date().toLocaleTimeString("es-CO", { hour: "numeric", minute: "2-digit" })}).`);
  };

  const enviadoA = acta?.customer_link_sent_to;
  return (
    <div className="acta-body">
      {error && <p className="form-error" role="alert">{error}</p>}
      <div className="annex-signatures">
        <div className={`annex-signer ${acta?.technician_signed_at ? "is-signed" : ""}`}>
          <div className="annex-signer-head">
            <strong>Técnico</strong>
            {acta?.technician_signed_at
              ? <span className="acta-chip is-done"><CheckCircleIcon size={16} /> Firmado</span>
              : <span className="acta-chip is-pending"><ClockIcon size={16} /> Pendiente</span>}
          </div>
          {acta?.technician_signed_at ? (
            <p className="acta-lead">Firmó el {cuando(acta.technician_signed_at)}</p>
          ) : canSign ? (
            <>
              <p className="acta-lead">Firma con el dedo dentro del recuadro.</p>
              <SignaturePad onCapture={(firma) => firmaTecnico.mutate(firma)} disabled={firmaTecnico.isPending} />
            </>
          ) : <p className="acta-lead">Falta la firma del técnico.</p>}
        </div>

        <div className={`annex-signer ${acta?.customer_signed_at ? "is-signed" : ""}`}>
          <div className="annex-signer-head">
            <strong>Cliente</strong>
            {acta?.customer_signed_at
              ? <span className="acta-chip is-done"><CheckCircleIcon size={16} /> Firmado</span>
              : enviadoA
                ? <span className="acta-chip is-current"><SendIcon size={14} /> Enlace enviado</span>
                : <span className="acta-chip is-pending"><ClockIcon size={16} /> Pendiente</span>}
          </div>
          {acta?.customer_signed_at ? (
            <p className="acta-lead">{acta.customer_name ? `${acta.customer_name} firmó` : "Firmó"} el {cuando(acta.customer_signed_at)}</p>
          ) : !canSign ? (
            <p className="acta-lead">Falta la firma del cliente.</p>
          ) : enPersona ? (
            <>
              <p className="acta-lead">Entrégale el celular al cliente para que escriba su nombre y firme.</p>
              <div className="field">
                <label htmlFor="firma-cliente-nombre">Nombre de quien firma</label>
                <input id="firma-cliente-nombre" value={nombre} onChange={(e) => setNombre(e.target.value)} autoComplete="off" />
              </div>
              <SignaturePad onCapture={(firma) => firmaCliente.mutate(firma)} disabled={!nombre.trim() || firmaCliente.isPending} />
              <button type="button" className="link-button" onClick={() => setEnPersona(false)}>Mejor enviarle el enlace</button>
            </>
          ) : (
            <>
              {enviadoA ? (
                <>
                  <p className="acta-lead">
                    Enlace enviado a <strong>{enviadoA}</strong>
                    {acta?.customer_link_expires_at && <>, vence el {new Date(acta.customer_link_expires_at).toLocaleDateString("es-CO", { day: "numeric", month: "short" })}</>}.
                  </p>
                  {consulta && <p className="acta-hint" role="status">{consulta}</p>}
                  <div className="acta-actions signature-actions">
                    <button type="button" className="acta-btn is-primary" onClick={consultar} disabled={isFetching}>
                      {isFetching ? "Consultando…" : "Consultar si ya firmó"}
                    </button>
                    <button type="button" className="acta-btn" onClick={() => enlace.mutate()} disabled={enlace.isPending}>
                      {enlace.isPending ? "Enviando…" : "Reenviar enlace"}
                    </button>
                  </div>
                </>
              ) : (
                <>
                  <p className="acta-lead">Le llega un enlace al correo y firma desde su teléfono.</p>
                  <div className="acta-actions signature-actions">
                    <button type="button" className="acta-btn is-primary" onClick={() => enlace.mutate()} disabled={enlace.isPending}>
                      {enlace.isPending ? "Enviando…" : "Enviar enlace por correo"}
                    </button>
                  </div>
                </>
              )}
              <p className="acta-hint">
                ¿No tiene correo o internet?{" "}
                <button type="button" className="link-button" onClick={() => setEnPersona(true)}>Que firme aquí, en este celular</button>
              </p>
            </>
          )}
        </div>
      </div>

      {acta?.is_fully_signed && (
        <div className="acta-actions signature-actions">
          <button type="button" className="acta-btn" onClick={async () => {
            window.open(await fetchAttestationPdfObjectUrl(acta.id), "_blank");
          }}>Descargar acta firmada (PDF)</button>
        </div>
      )}
    </div>
  );
}
