import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import "../billing/billing.css";
import "../programs/programs.css";
import "./sales.css";
import { useAuth } from "@/features/auth/AuthContext";
import { apiErrorMessage } from "@/features/field-ops/module5Api";
import { FormRenderer } from "@/features/programs/FormRenderer";
import { SignatureImage } from "./CaseFormPage";
import {
  caseEvents,
  caseProject,
  docKeys,
  errorCode,
  getCase,
  fileBlobUrl,
  getCaseForm,
  listDocuments,
  openCaseFile,
  reviewDocument,
  salesKeys,
  setSubstatus,
  transitionCase,
  uploadExtraDocument,
  type CaseDocument,
} from "./api";

export const SUBSTATUS_LABELS: Record<string, string> = {
  pending_review: "En revisión", returned: "Devuelto al vendedor", ready_to_submit: "Listo para el programa",
  submitted_to_program: "Sometido al programa", program_review: "En revisión del programa",
};
// El avance con el programa, en orden (sub-estados de "Pendiente de aprobación").
const AVANCE = ["pending_review", "ready_to_submit", "submitted_to_program", "program_review"];

/**
 * Revisión del expediente por Administración (módulos 3 y 4): los documentos
 * uno por uno, lo que respondió el cliente, la firma, el avance con el
 * programa y la decisión (aprobar, devolver, poner en espera o rechazar).
 */
export function CaseReviewPage() {
  const { caseId } = useParams<{ caseId: string }>();
  const { hasPermission } = useAuth();
  const qc = useQueryClient();
  const { data: form, isLoading, error } = useQuery({ queryKey: salesKeys.form(caseId!), queryFn: () => getCaseForm(caseId!), retry: false });
  const { data: docs } = useQuery({ queryKey: docKeys.list(caseId!), queryFn: () => listDocuments(caseId!) });
  const { data: eventos } = useQuery({ queryKey: docKeys.events(caseId!), queryFn: () => caseEvents(caseId!) });
  // Un expediente creado sin programa (antes del módulo 2 o por otra vía) no
  // tiene formulario: igual se revisa, se decide y se cierra.
  const sinFormulario = errorCode(error) === "program_required";
  const { data: caseData } = useQuery({ queryKey: ["case", caseId], queryFn: () => getCase(caseId!), enabled: sinFormulario });
  const veProyectos = hasPermission("projects.read_all") || hasPermission("projects.read_assigned");
  const { data: proyecto } = useQuery({ queryKey: ["case-project", caseId], queryFn: () => caseProject(caseId!),
    enabled: veProyectos, retry: false });
  const refrescar = () => Promise.all([
    qc.invalidateQueries({ queryKey: salesKeys.form(caseId!) }),
    qc.invalidateQueries({ queryKey: docKeys.list(caseId!) }),
    qc.invalidateQueries({ queryKey: docKeys.events(caseId!) }),
    qc.invalidateQueries({ queryKey: docKeys.queue }),
    qc.invalidateQueries({ queryKey: ["case-board"] }),
  ]);

  if (isLoading) return <p>Cargando…</p>;
  if (!form && !sinFormulario) return <p className="form-error">{apiErrorMessage(error)}</p>;
  const c = form?.case ?? caseData;
  if (!c) return <p>Cargando…</p>;
  const lista = docs ?? [];
  const pendientes = lista.filter((d) => d.review_status === "pending").length;
  const rechazados = lista.filter((d) => d.review_status === "rejected").length;
  const enRevision = ["pending_approval", "on_hold"].includes(c.stage_code);
  const nombre = (form?.answers["customer.full_name"] as string) || c.address_street || "Expediente";

  return (
    <div className="review-page">
      <Link to="/cases" className="acta-back"><span aria-hidden="true">‹</span> Expedientes</Link>
      <div className="review-grid">
        <div className="review-main">
          <article className="acta">
            <header className="acta-header">
              <div className="acta-title-row">
                <h1 className="acta-title">{nombre}</h1>
                <span className={`billing-chip ${c.substatus_code === "returned" ? "is-rejected" : enRevision ? "is-submitted" : "is-paid"}`}>
                  {c.stage_label}{c.substatus_code && SUBSTATUS_LABELS[c.substatus_code] ? ` · ${SUBSTATUS_LABELS[c.substatus_code]}` : ""}
                </span>
              </div>
              <dl className="acta-meta">
                <div><dt>Expediente</dt><dd className="acta-data">{c.case_number}</dd></div>
                <div><dt>Dirección</dt><dd>{[c.address_street, c.address_unit, c.address_city, c.address_state].filter(Boolean).join(", ")}</dd></div>
                <div><dt>Enviado</dt><dd>{c.submitted_at ? fecha(c.submitted_at) : "—"}</dd></div>
                <div><dt>Formulario</dt><dd>{form ? `versión ${form.definition.version}` : "sin formulario"}</dd></div>
                {proyecto && <div><dt>Instalación</dt><dd><Link to={`/projects/${proyecto.id}`} className="acta-link">{proyecto.title} ›</Link></dd></div>}
                {c.approval_code && <div><dt>Código de aprobación</dt><dd className="acta-data">{c.approval_code}</dd></div>}
                {c.application_number && <div><dt>N.º de solicitud</dt><dd className="acta-data">{c.application_number}</dd></div>}
              </dl>
              {c.stage_reason && (c.substatus_code === "returned" || ["on_hold", "rejected"].includes(c.stage_code)) && (
                <p className="acta-note">Motivo: {c.stage_reason}</p>
              )}
            </header>

            <section className="review-section" aria-labelledby="rev-docs">
              <div className="review-section-head">
                <h2 id="rev-docs">Documentos</h2>
                <span className="review-tally">
                  <span className="billing-chip is-preparing">{pendientes} por revisar</span>
                  {rechazados > 0 && <span className="billing-chip is-rejected">{rechazados} rechazados</span>}
                </span>
              </div>
              {lista.length === 0 && <p className="acta-empty">Este expediente no tiene documentos.</p>}
              <DocumentGroups docs={lista} canReview={enRevision && hasPermission("documents.review")} onDone={refrescar} />
              {hasPermission("documents.manage") && !["closed"].includes(c.stage_code) && <ExtraDocument caseId={caseId!} onDone={refrescar} />}
            </section>

            {sinFormulario && (
              <p className="acta-note">Este expediente no tiene programa ni formulario: se creó antes del formulario por programa o por otra vía.
                Se puede revisar su historial, decidir y cerrar{proyecto ? ", y su instalación está en el enlace de arriba" : ""}.</p>
            )}

            {form?.acceptance && (
              <section className="review-section">
                <h2>Términos y firma</h2>
                <div className="sales-signed">
                  <SignatureImage caseId={caseId!} version={form.acceptance.accepted_at} />
                  <div>
                    <strong>✓ Aceptó y firmó {form.acceptance.customer_name}</strong>
                    <span>{fecha(form.acceptance.accepted_at)}{form.acceptance.terms_version ? ` · términos ${form.acceptance.terms_version}` : ""}</span>
                  </div>
                </div>
              </section>
            )}

            {form && <section className="review-section">
              <h2>Lo que respondió el cliente</h2>
              <FormRenderer evaluation={form.evaluation} answers={form.answers} onChange={() => undefined} disabled
                media={{ upload: async () => "", open: openCaseFile,
                  fileName: (id) => form.files.find((f) => f.id === id)?.original_filename ?? undefined }} />
            </section>}
          </article>
        </div>

        <aside className="review-side">
          <Decision caseId={caseId!} stage={c.stage_code} substatus={c.substatus_code} pendientes={pendientes}
            rechazados={rechazados} onDone={refrescar} />
          {hasPermission("cases.close_admin") && c.stage_code !== "closed" && (
            <CloseCase caseId={caseId!} onDone={refrescar} />
          )}
          <article className="acta review-history">
            <h2>Historial</h2>
            <ol className="acta-history">
              {[...(eventos ?? [])].reverse().map((e) => (
                <li key={e.id} className={e.to_substatus_code === "returned" || e.to_stage_code === "rejected" ? "is-returned"
                  : e.to_stage_code === "approved" ? "is-confirmed" : ""}>
                  {e.from_stage_code === e.to_stage_code && e.to_substatus_label
                    ? e.to_substatus_label
                    : e.to_stage_label}
                  <span>{fecha(e.occurred_at)}</span>
                  {e.reason && <p>{e.reason}</p>}
                </li>
              ))}
            </ol>
          </article>
        </aside>
      </div>
    </div>
  );
}

/** «8 oct 2026, 5:33 a. m.»: con el mes en letras no se confunde día y mes,
 *  que en EE. UU. se leen al revés («8/10/2026» es 10 de agosto allá). QA-REG-08. */
function fecha(iso: string) {
  return new Date(iso).toLocaleString("es-US", {
    day: "numeric", month: "short", year: "numeric", hour: "numeric", minute: "2-digit",
  });
}

// ---------------------------------------------------------------------------
// Documentos
// ---------------------------------------------------------------------------

function DocumentGroups({ docs, canReview, onDone }: { docs: CaseDocument[]; canReview: boolean; onDone: () => void }) {
  const grupos = docs.reduce<Record<string, CaseDocument[]>>((acc, d) => ((acc[d.step_title] ??= []).push(d), acc), {});
  return (
    <>
      {Object.entries(grupos).map(([paso, items]) => (
        <div key={paso} className="review-doc-group">
          <h3 className="acta-section-title">{paso}</h3>
          <ul className="review-docs">
            {items.map((d) => <DocumentCard key={d.id} doc={d} canReview={canReview} onDone={onDone} />)}
          </ul>
        </div>
      ))}
    </>
  );
}

function DocumentCard({ doc, canReview, onDone }: { doc: CaseDocument; canReview: boolean; onDone: () => void }) {
  const [rechazando, setRechazando] = useState(false);
  const [nota, setNota] = useState("");
  const [error, setError] = useState<string | null>(null);
  const revisar = useMutation({
    mutationFn: ({ status, notes }: { status: "accepted" | "rejected"; notes?: string }) => reviewDocument(doc.id, status, notes),
    onSuccess: () => { setRechazando(false); setNota(""); setError(null); onDone(); },
    onError: (e) => setError(apiErrorMessage(e)),
  });
  const chip = { pending: "is-preparing", accepted: "is-accepted", rejected: "is-rejected" }[doc.review_status];
  return (
    <li className={`review-doc is-${doc.review_status}`}>
      <Thumb doc={doc} />
      <div className="review-doc-body">
        <div className="review-doc-title">
          <strong>{doc.label}</strong>
          <span className={`billing-chip ${chip}`}>{doc.review_label}</span>
        </div>
        <small>
          {doc.original_filename ?? "archivo"}
          {doc.watermarked && " · marca GPS"}
          {doc.latitude != null && doc.longitude != null && ` · ${doc.latitude.toFixed(4)}, ${doc.longitude.toFixed(4)}`}
          {doc.captured_at && ` · ${fecha(doc.captured_at)}`}
        </small>
        {doc.review_notes && <p className="review-doc-note">{doc.review_notes}</p>}
        {doc.reviewed_by && <small>Revisó {doc.reviewed_by}{doc.reviewed_at ? `, ${fecha(doc.reviewed_at)}` : ""}</small>}
        {error && <p className="form-error-text" role="alert">{error}</p>}
        {canReview && (rechazando ? (
          <form className="review-reject" onSubmit={(e) => { e.preventDefault(); revisar.mutate({ status: "rejected", notes: nota }); }}>
            <label className="form-label" htmlFor={`nota-${doc.id}`}>¿Por qué se rechaza? El vendedor lo verá.</label>
            <input id={`nota-${doc.id}`} value={nota} onChange={(e) => setNota(e.target.value)} autoFocus
              placeholder="Ej.: la foto está borrosa, no se lee el número" />
            <div className="acta-actions">
              <button type="submit" className="acta-btn is-primary" disabled={!nota.trim() || revisar.isPending}>Rechazar</button>
              <button type="button" className="acta-btn is-quiet" onClick={() => setRechazando(false)}>Cancelar</button>
            </div>
          </form>
        ) : (
          <div className="acta-actions">
            {doc.review_status !== "accepted" && (
              <button type="button" className="acta-btn is-line" disabled={revisar.isPending}
                onClick={() => revisar.mutate({ status: "accepted" })}>✓ Aceptar</button>
            )}
            {doc.review_status !== "rejected" && (
              <button type="button" className="acta-btn is-quiet" onClick={() => setRechazando(true)}>Rechazar</button>
            )}
          </div>
        ))}
      </div>
    </li>
  );
}

function Thumb({ doc }: { doc: CaseDocument }) {
  const esImagen = (doc.mime_type ?? "").startsWith("image/");
  const [url, setUrl] = useState<string | null>(null);
  useEffect(() => {
    if (!esImagen) return;
    let vivo = true;
    let obj: string | null = null;
    fileBlobUrl(doc.id).then((u) => { obj = u; if (vivo) setUrl(u); }).catch(() => undefined);
    return () => { vivo = false; if (obj) URL.revokeObjectURL(obj); };
  }, [doc.id, esImagen]);
  const icono = doc.mime_type === "application/pdf" ? "PDF" : (doc.mime_type ?? "").startsWith("video/") ? "▶" : "🗎";
  return (
    <button type="button" className="review-thumb" onClick={() => openCaseFile(doc.id)} aria-label={`Abrir ${doc.label}`}>
      {esImagen ? (url ? <img src={url} alt="" /> : <span className="is-loading" />) : <span>{icono}</span>}
    </button>
  );
}

function ExtraDocument({ caseId, onDone }: { caseId: string; onDone: () => void }) {
  const [abierto, setAbierto] = useState(false);
  const [label, setLabel] = useState("");
  const [archivo, setArchivo] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const subir = useMutation({
    mutationFn: () => uploadExtraDocument(caseId, label, archivo!),
    onSuccess: () => { setAbierto(false); setLabel(""); setArchivo(null); setError(null); onDone(); },
    onError: (e) => setError(apiErrorMessage(e)),
  });
  if (!abierto) {
    return <button type="button" className="acta-btn is-quiet review-add" onClick={() => setAbierto(true)}>+ Agregar documento</button>;
  }
  return (
    <form className="review-extra" onSubmit={(e) => { e.preventDefault(); subir.mutate(); }}>
      <div className="form-field">
        <label className="form-label" htmlFor="extra-label">Nombre del documento</label>
        <input id="extra-label" value={label} onChange={(e) => setLabel(e.target.value)} placeholder="Ej.: Factura de luz de septiembre" />
      </div>
      <div className="form-field">
        <label className="form-label" htmlFor="extra-file">Archivo (foto o PDF, hasta 15 MB)</label>
        <input id="extra-file" type="file" accept="image/*,application/pdf" onChange={(e) => setArchivo(e.target.files?.[0] ?? null)} />
      </div>
      {error && <p className="form-error-text" role="alert">{error}</p>}
      <div className="acta-actions">
        <button type="submit" className="acta-btn is-primary" disabled={!label.trim() || !archivo || subir.isPending}>
          {subir.isPending ? "Subiendo…" : "Subir"}
        </button>
        <button type="button" className="acta-btn is-quiet" onClick={() => setAbierto(false)}>Cancelar</button>
      </div>
    </form>
  );
}

// ---------------------------------------------------------------------------
// Decisión (módulo 4)
// ---------------------------------------------------------------------------

type Accion = "return" | "approve" | "on_hold" | "reject" | null;

function Decision({ caseId, stage, substatus, pendientes, rechazados, onDone }: {
  caseId: string; stage: string; substatus: string | null; pendientes: number; rechazados: number; onDone: () => void;
}) {
  const { hasPermission } = useAuth();
  const [accion, setAccion] = useState<Accion>(null);
  const [motivo, setMotivo] = useState("");
  const [codigo, setCodigo] = useState("");
  const [solicitud, setSolicitud] = useState("");
  const [error, setError] = useState<string | null>(null);
  const hecho = () => { setAccion(null); setMotivo(""); setError(null); onDone(); };
  const fallo = (e: unknown) => setError(apiErrorMessage(e));
  const avance = useMutation({ mutationFn: (s: string) => setSubstatus(caseId, s), onSuccess: hecho, onError: fallo });
  const decidir = useMutation({
    mutationFn: () => accion === "return"
      ? setSubstatus(caseId, "returned", motivo)
      : transitionCase(caseId, {
        to_stage: accion === "approve" ? "approved" : accion === "on_hold" ? "on_hold" : "rejected",
        reason: motivo || undefined,
        ...(accion === "approve" ? { approval_code: codigo || undefined, application_number: solicitud || undefined } : {}),
      }),
    onSuccess: hecho, onError: fallo,
  });

  const puedeRevisar = hasPermission("cases.review");
  const puedeAprobar = hasPermission("cases.approve");
  const enRevision = stage === "pending_approval";
  if (!["pending_approval", "on_hold"].includes(stage)) {
    return (
      <article className="acta review-decision">
        <h2>Decisión</h2>
        <p className="acta-empty">{stage === "new_prospect" ? "El vendedor todavía no lo envía a revisión."
          : stage === "rejected" ? "Rechazado. El vendedor puede corregirlo y volver a enviarlo a revisión."
          : stage === "closed" ? "Cerrado. Ya no sigue en el flujo."
          : "Este expediente ya pasó la revisión."}</p>
      </article>
    );
  }
  const devuelto = substatus === "returned";
  const bloqueoAprobar = rechazados ? `Hay ${rechazados} documento(s) rechazado(s): devuélvelo para que los reemplacen.`
    : pendientes ? `Faltan ${pendientes} documento(s) por revisar.` : null;
  const necesitaMotivo = accion === "return" || accion === "reject" || accion === "on_hold";

  return (
    <article className="acta review-decision">
      <h2>Decisión</h2>
      {enRevision && (
        <>
          <h3 className="acta-section-title">Avance con el programa</h3>
          <ol className="review-progress">
            {AVANCE.map((s, i) => {
              const actual = AVANCE.indexOf(substatus ?? "pending_review");
              const hechoPaso = !devuelto && i <= actual;
              return (
                <li key={s} className={`${hechoPaso ? "is-done" : ""}${s === substatus ? " is-current" : ""}`}>
                  <span aria-hidden="true">{hechoPaso ? "✓" : i + 1}</span>
                  {puedeRevisar && !devuelto && i === actual + 1 ? (
                    <button type="button" className="acta-link" disabled={avance.isPending} onClick={() => avance.mutate(s)}>
                      Marcar «{SUBSTATUS_LABELS[s]}»
                    </button>
                  ) : SUBSTATUS_LABELS[s]}
                </li>
              );
            })}
          </ol>
          {devuelto && <p className="acta-note">Devuelto al vendedor: espera a que lo corrija y lo reenvíe.</p>}
        </>
      )}

      {error && <p className="form-error" role="alert">{error}</p>}

      {accion === null ? (
        <div className="review-actions">
          {puedeAprobar && (
            <button type="button" className="acta-btn is-primary" onClick={() => setAccion("approve")} disabled={!!bloqueoAprobar || devuelto}>
              Aprobar
            </button>
          )}
          {bloqueoAprobar && puedeAprobar && <p className="review-hint">{bloqueoAprobar}</p>}
          {enRevision && puedeRevisar && !devuelto && (
            <button type="button" className="acta-btn is-line" onClick={() => setAccion("return")}>Devolver al vendedor</button>
          )}
          {enRevision && puedeAprobar && (
            <button type="button" className="acta-btn is-quiet" onClick={() => setAccion("on_hold")}>Poner en espera del programa</button>
          )}
          {puedeAprobar && <button type="button" className="acta-btn is-quiet review-danger" onClick={() => setAccion("reject")}>Rechazar</button>}
        </div>
      ) : (
        <form className="review-form" onSubmit={(e) => { e.preventDefault(); decidir.mutate(); }}>
          <h3 className="acta-section-title">
            {{ approve: "Aprobar", return: "Devolver al vendedor", on_hold: "Poner en espera", reject: "Rechazar" }[accion]}
          </h3>
          {accion === "approve" && (
            <>
              <div className="form-field">
                <label className="form-label" htmlFor="ap-code">Código de aprobación del programa</label>
                <input id="ap-code" value={codigo} onChange={(e) => setCodigo(e.target.value)} autoFocus />
              </div>
              <div className="form-field">
                <label className="form-label" htmlFor="ap-app">Número de solicitud</label>
                <input id="ap-app" value={solicitud} onChange={(e) => setSolicitud(e.target.value)} />
              </div>
              <p className="review-hint">Al aprobar se crea el proyecto de instalación.</p>
            </>
          )}
          <div className="form-field">
            <label className="form-label" htmlFor="dec-motivo">
              {accion === "return" ? "Qué debe corregir el vendedor" : accion === "approve" ? "Nota (opcional)" : "Motivo"}
            </label>
            <textarea id="dec-motivo" rows={3} value={motivo} onChange={(e) => setMotivo(e.target.value)} autoFocus={accion !== "approve"} />
          </div>
          <div className="acta-actions">
            <button type="submit" className={`acta-btn ${accion === "reject" ? "is-line review-danger" : "is-primary"}`}
              disabled={decidir.isPending || (necesitaMotivo && !motivo.trim())}>
              {decidir.isPending ? "Guardando…" : "Confirmar"}
            </button>
            <button type="button" className="acta-btn is-quiet" onClick={() => { setAccion(null); setError(null); }}>Cancelar</button>
          </div>
        </form>
      )}
    </article>
  );
}

/** Cierre administrativo (desde cualquier etapa, con `cases.close_admin`). Pide motivo. */
function CloseCase({ caseId, onDone }: { caseId: string; onDone: () => void }) {
  const [abierto, setAbierto] = useState(false);
  const [motivo, setMotivo] = useState("");
  const [error, setError] = useState<string | null>(null);
  const cerrar = useMutation({
    mutationFn: () => transitionCase(caseId, { to_stage: "closed", reason: motivo }),
    onSuccess: () => { setAbierto(false); setMotivo(""); setError(null); onDone(); },
    onError: (e) => setError(apiErrorMessage(e)),
  });
  return (
    <article className="acta review-close">
      <h2>Cerrar expediente</h2>
      {!abierto ? (
        <>
          <p className="review-hint">Lo saca del flujo en cualquier etapa (cliente se mudó, duplicado, desistió…). Queda en el historial con su motivo.</p>
          <button type="button" className="acta-btn is-quiet review-danger" onClick={() => setAbierto(true)}>Cerrar expediente…</button>
        </>
      ) : (
        <form className="review-form" onSubmit={(e) => { e.preventDefault(); cerrar.mutate(); }}>
          <div className="form-field">
            <label className="form-label" htmlFor="close-motivo">Motivo del cierre</label>
            <textarea id="close-motivo" rows={3} value={motivo} onChange={(e) => setMotivo(e.target.value)} autoFocus />
          </div>
          {error && <p className="form-error" role="alert">{error}</p>}
          <div className="acta-actions">
            <button type="submit" className="acta-btn is-line review-danger" disabled={!motivo.trim() || cerrar.isPending}>
              {cerrar.isPending ? "Cerrando…" : "Confirmar cierre"}</button>
            <button type="button" className="acta-btn is-quiet" onClick={() => setAbierto(false)}>Cancelar</button>
          </div>
        </form>
      )}
    </article>
  );
}
