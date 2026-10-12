import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import "../billing/billing.css";
import "../programs/programs.css";
import "./sales.css";
import { useAuth } from "@/features/auth/AuthContext";
import { apiErrorMessage } from "@/features/field-ops/module5Api";
import { SignaturePad } from "@/features/field-ops/SignaturePad";
import { previewVersion } from "@/features/programs/api";
import { FormRenderer, type MediaSupport } from "@/features/programs/FormRenderer";
import { apiClient } from "@/lib/apiClient";
import { useGeolocation } from "@/lib/useGeolocation";
import type { Evaluation } from "@/types/programs";
import {
  acceptTerms,
  getCaseForm,
  getCase,
  programOptions,
  openCaseFile,
  saveStep,
  salesKeys,
  setCaseProgram,
  submitCase,
  uploadCaseFile,
} from "./api";

const REVIEW = "__review__";

/**
 * El expediente del vendedor, paso a paso (módulo 2): el formulario del
 * programa con el mismo motor de la vista previa, fotos con cámara y GPS,
 * términos con firma del cliente, resumen y envío a revisión. Cada paso se
 * guarda al avanzar: si se cae la señal, lo guardado no se pierde.
 */
export function CaseFormPage() {
  const { caseId } = useParams<{ caseId: string }>();
  const qc = useQueryClient();
  // La evaluación en vivo exige `programs.read`. Contabilidad y Gerencia solo
  // consultan el formulario: les basta la evaluación que trae el servidor, y
  // pedirla en vivo les daba 403 (QA-REG-10).
  const evaluaEnVivo = useAuth().hasPermission("programs.read");
  const geo = useGeolocation();
  useEffect(() => { geo.request(); }, [geo.request]);
  // Sin recargar al volver a la ventana: abrir la cámara o el selector de
  // archivos le quita el foco, y la recarga pisaba lo escrito sin guardar.
  const { data: form, isLoading, error: errCarga } = useQuery({
    queryKey: salesKeys.form(caseId!), queryFn: () => getCaseForm(caseId!), retry: false,
    refetchOnWindowFocus: false,
  });
  const [answers, setAnswers] = useState<Record<string, unknown>>({});
  const [paso, setPaso] = useState<string | null>(null);
  const [evaluacion, setEvaluacion] = useState<Evaluation | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  // Nombres de lo subido en esta sesión, para mostrarlos antes de guardar el paso.
  const [subidos, setSubidos] = useState<Record<string, string>>({});

  // Lo guardado en el servidor es la base; lo que se está escribiendo en esta
  // pantalla manda encima, para que una recarga nunca borre lo no guardado.
  const [sucio, setSucio] = useState<Set<string>>(new Set());
  useEffect(() => {
    if (!form) return;
    setAnswers((local) => ({ ...form.answers, ...Object.fromEntries([...sucio].filter((k) => k in local).map((k) => [k, local[k]])) }));
    setEvaluacion((e) => e ?? form.evaluation);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [form]);
  const cambiar = (k: string, v: unknown) => {
    setAnswers((a) => ({ ...a, [k]: v }));
    setSucio((s) => new Set(s).add(k));
  };
  const versionId = (form?.definition as { version_id?: string } | undefined)?.version_id;
  const firma = useMemo(() => JSON.stringify(answers), [answers]);
  // Evaluación en vivo con el mismo motor: una condición aparece al marcarla.
  useEffect(() => {
    if (!versionId || !evaluaEnVivo) return;
    let vivo = true;
    const t = setTimeout(() => previewVersion(versionId, answers).then((r) => vivo && setEvaluacion(r)).catch(() => undefined), 300);
    return () => { vivo = false; clearTimeout(t); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [versionId, firma]);

  const refrescar = () => qc.invalidateQueries({ queryKey: salesKeys.form(caseId!) });
  const pasos = form?.definition.steps ?? [];
  // El paso se fija al abrir el expediente —el primero incompleto según lo
  // GUARDADO— y solo cambia cuando el vendedor navega. Antes se recalculaba con
  // la evaluación en vivo: al llenar el último campo de un paso, la pantalla
  // saltaba sola al siguiente sin guardar, y lo escrito se perdía (12 oct 2026).
  const inicial = pasos.find((s) => !form?.evaluation.steps.find((e) => e.code === s.code)?.complete)?.code ?? pasos[0]?.code;
  useEffect(() => { if (!paso && inicial) setPaso(inicial); }, [paso, inicial]);
  const actual = paso ?? inicial;
  // Pasos con algo escrito sin guardar: no se marcan completos ni dejan enviar,
  // porque el servidor revisa lo guardado y no lo que hay en pantalla.
  const sinGuardar = new Set(pasos.filter((s) => s.fields.some((f) => sucio.has(f.key))).map((s) => s.code));

  // La firma dibujada en el paso de autorización se guarda junto con el paso.
  const firmaPendiente = useRef<(() => Promise<unknown>) | null>(null);
  const registrarFirma = useCallback((f: (() => Promise<unknown>) | null) => { firmaPendiente.current = f; }, []);

  const guardar = useMutation({
    mutationFn: async (siguiente: string | null) => {
      if (firmaPendiente.current) {
        await firmaPendiente.current();
        firmaPendiente.current = null;
      }
      const def = pasos.find((s) => s.code === actual);
      if (!def) return siguiente;
      const delPaso = Object.fromEntries(def.fields.filter((f) => f.key in answers && !["signature", "system_datetime", "system_user", "terms_checkbox", "info"].includes(f.type))
        .map((f) => [f.key, answers[f.key]]));
      if (Object.keys(delPaso).length) await saveStep(caseId!, def.code, delPaso, geo.coords);
      return siguiente;
    },
    onSuccess: async (siguiente) => {
      setError(null);
      const def = pasos.find((st) => st.code === actual);
      if (def) setSucio((s) => { const n = new Set(s); def.fields.forEach((f) => n.delete(f.key)); return n; });
      await refrescar();
      if (siguiente) { setPaso(siguiente); window.scrollTo({ top: 0 }); }
    },
    onError: (e) => setError(apiErrorMessage(e)),
  });

  if (isLoading) return <p>Cargando…</p>;
  if (errCarga) {
    const sinPrograma = (errCarga as { response?: { data?: { code?: string } } })?.response?.data?.code === "program_required";
    return sinPrograma ? <ChooseProgram caseId={caseId!} onDone={refrescar} /> : <p className="form-error">{apiErrorMessage(errCarga)}</p>;
  }
  if (!form || !evaluacion) return null;

  const c = form.case;
  const media: MediaSupport = {
    upload: async (key, file) => {
      const id = await uploadCaseFile(caseId!, key, file, geo.coords);
      setSubidos((m) => ({ ...m, [id]: file.name }));
      // El adjunto queda guardado en su paso en el momento: no depende de
      // tocar "Guardar y seguir" ni de no cambiar de paso.
      const paso = pasos.find((st) => st.fields.some((f) => f.key === key));
      if (paso) await saveStep(caseId!, paso.code, { [key]: id }, geo.coords);
      return id;
    },
    fileName: (id) => subidos[id] ?? form.files.find((f) => f.id === id)?.original_filename ?? undefined,
    open: openCaseFile,
  };
  const idx = pasos.findIndex((s) => s.code === actual);
  const siguiente = actual === REVIEW ? null : idx >= 0 && idx < pasos.length - 1 ? pasos[idx + 1].code : REVIEW;
  const esAutorizacion = pasos.find((s) => s.code === actual)?.fields.some((f) => f.type === "terms_checkbox");
  const devuelto = c.stage_code === "pending_approval" && c.substatus_code === "returned";
  const rechazado = c.stage_code === "rejected";
  // Lo que Administración rechazó y sigue vigente: el vendedor lo reemplaza
  // en su paso y el nuevo archivo entra como pendiente (módulo 3).
  const vigentes = new Set(Object.values(answers).filter((v): v is string => typeof v === "string"));
  const rechazados = form.files.filter((f) => f.review_status === "rejected" && vigentes.has(f.id)).map((f) => {
    const st = pasos.find((x) => x.fields.some((fl) => fl.key === f.field_key));
    return { id: f.id, notes: f.review_notes, paso: st?.code ?? actual,
      label: st?.fields.find((fl) => fl.key === f.field_key)?.label ?? f.field_key };
  });

  return (
    <div className="sales-page sales-form">
      <Link to="/sales" className="acta-back"><span aria-hidden="true">‹</span> Mi día</Link>
      <article className="acta">
        <header className="acta-header">
          <div className="acta-title-row">
            <h1 className="acta-title">{(answers["customer.full_name"] as string) || c.address_street || "Expediente"}</h1>
            <span className={`billing-chip ${form.editable ? "is-draft" : "is-paid"}`}>{c.stage_label}</span>
          </div>
          <dl className="acta-meta">
            <div><dt>Expediente</dt><dd className="acta-data">{c.case_number}</dd></div>
            <div><dt>Dirección</dt><dd>{[c.address_street, c.address_unit, c.address_city].filter(Boolean).join(", ")}</dd></div>
            <div><dt>Formulario</dt><dd>versión {form.definition.version}</dd></div>
            <div><dt>Avance</dt><dd>{evaluacion.steps.filter((s) => s.complete).length} de {evaluacion.steps.length} pasos</dd></div>
          </dl>
          {devuelto && <p className="acta-note">Administración lo devolvió: {c.stage_reason ?? "revisa y corrige"}. Al terminar, vuelve a enviarlo.</p>}
          {rechazado && <p className="acta-note">Administración lo rechazó: {c.stage_reason ?? "sin motivo"}. Si se puede corregir, ajústalo y vuelve a enviarlo a revisión.</p>}
          {rechazados.length > 0 && (
            <div className="sales-rejected" role="alert">
              <strong>Documentos rechazados: súbelos de nuevo</strong>
              <ul>{rechazados.map((r) => (
                <li key={r.id}><button type="button" className="acta-link" onClick={() => setPaso(r.paso)}>{r.label}</button>: {r.notes}</li>
              ))}</ul>
            </div>
          )}
          {!form.editable && <p className="acta-note">Ya está enviado; se corrige si Administración lo devuelve.</p>}
        </header>

        <ol className="preview-steps sales-steps">
          {evaluacion.steps.map((s, n) => { const listo = s.complete && !sinGuardar.has(s.code); return (
            <li key={s.code}>
              <button type="button" className={`${s.code === actual ? "is-on" : ""}${listo ? " is-complete" : ""}`}
                title={sinGuardar.has(s.code) ? "Tiene cambios sin guardar" : undefined}
                onClick={() => form.editable ? guardar.mutate(s.code) : setPaso(s.code)}>
                {listo ? "✓" : n + 1}<span>{s.title}</span>
              </button>
            </li>
          ); })}
          <li><button type="button" className={actual === REVIEW ? "is-on" : ""} onClick={() => form.editable ? guardar.mutate(REVIEW) : setPaso(REVIEW)}>
            {evaluacion.can_submit && sinGuardar.size === 0 ? "✓" : "→"}<span>Enviar</span></button></li>
        </ol>

        {error && <p className="form-error" role="alert">{error}</p>}
        {aviso && <p className="info-banner" role="status">{aviso}</p>}

        {actual === REVIEW ? (
          <Review caseId={caseId!} evaluation={evaluacion} unsaved={sinGuardar} editable={form.editable} resubmit={devuelto || rechazado}
            onGo={(code) => setPaso(code)} onSent={async () => { setAviso("Enviado a revisión. Administración lo revisa y te avisa si hay que corregir."); await refrescar(); }}
            onError={setError} />
        ) : (
          <>
            {esAutorizacion && form.terms && (
              <TermsAndSignature caseId={caseId!} terms={form.terms} acceptance={form.acceptance} editable={form.editable}
                defaultName={(answers["customer.full_name"] as string) ?? ""} coords={geo.coords}
                onSigned={refrescar} onError={setError} registerPending={registrarFirma} />
            )}
            <FormRenderer evaluation={esAutorizacion && form.terms ? { ...evaluacion, steps: evaluacion.steps.map((st) =>
              st.code === actual ? { ...st, title: "Otros datos", fields: st.fields.filter((f) => !isAuthField(f)) } : st) } : evaluacion}
              answers={answers} stepCode={actual} media={media} disabled={!form.editable}
              onChange={cambiar} />
            {form.editable && (
              <div className="sales-nav">
                <button type="button" className="acta-btn is-quiet" disabled={idx <= 0} onClick={() => guardar.mutate(pasos[idx - 1]?.code ?? null)}>‹ Anterior</button>
                <button type="button" className="acta-btn is-primary" disabled={guardar.isPending} onClick={() => guardar.mutate(siguiente)}>
                  {guardar.isPending ? "Guardando…" : siguiente === REVIEW ? "Guardar y revisar" : "Guardar y seguir"}
                </button>
              </div>
            )}
          </>
        )}
      </article>
    </div>
  );
}

function ChooseProgram({ caseId, onDone }: { caseId: string; onDone: () => void }) {
  const { hasPermission } = useAuth();
  const puedeElegir = hasPermission("cases.create");
  const { data: c } = useQuery({ queryKey: ["case", caseId], queryFn: () => getCase(caseId) });
  const { data: opciones } = useQuery({ queryKey: ["program-options"], queryFn: programOptions, enabled: puedeElegir });
  const [error, setError] = useState<string | null>(null);
  const elegir = useMutation({
    mutationFn: ({ p, z }: { p: string; z?: string }) => setCaseProgram(caseId, p, z),
    onSuccess: onDone, onError: (e) => setError(apiErrorMessage(e)),
  });
  const atras = <Link to={puedeElegir ? "/sales" : "/cases"} className="acta-back"><span aria-hidden="true">‹</span> {puedeElegir ? "Mi día" : "Expedientes"}</Link>;
  if (!c) return <p>Cargando…</p>;
  // Un expediente que ya avanzó sin programa (creado antes del formulario por
  // programa o por otra vía) no tiene formulario que llenar.
  if (c.stage_code !== "new_prospect") {
    return (
      <div className="sales-page">{atras}
        <article className="acta">
          <h1 className="acta-title">{c.address_street ?? c.case_number}</h1>
          <p className="acta-lead">{c.case_number} · {c.stage_label}</p>
          <p className="acta-note">Este expediente no tiene programa ni formulario: se creó antes del formulario por programa o por otra vía.</p>
          {(hasPermission("cases.review") || hasPermission("cases.approve")) && (
            <Link to={`/cases/${caseId}/review`} className="acta-btn is-line">Ver revisión e historial</Link>
          )}
        </article>
      </div>
    );
  }
  if (!puedeElegir) {
    return (
      <div className="sales-page">{atras}
        <article className="acta">
          <h1 className="acta-title">{c.address_street ?? c.case_number}</h1>
          <p className="acta-lead">{c.case_number} · Nuevo prospecto</p>
          <p className="acta-empty">El vendedor todavía no elige el programa ni llena el formulario de este expediente.</p>
        </article>
      </div>
    );
  }
  const lista = opciones?.options ?? [];
  return (
    <div className="sales-page">{atras}
      <article className="acta">
        <h1 className="acta-title">¿Para qué programa es?</h1>
        <p className="acta-lead">El formulario depende del programa. Una vez que guardes respuestas, ya no se cambia.</p>
        {opciones && !opciones.assigned && lista.length > 0 && (
          <p className="acta-note">No tienes zona asignada: se muestran todos los programas. Pídele a Administración que te asigne la tuya.</p>
        )}
        {error && <p className="form-error">{error}</p>}
        {opciones && lista.length === 0 && <p className="acta-empty">No hay programas activos con formulario publicado. Pídele a Administración que publique uno.</p>}
        <div className="sales-results">
          {lista.map((m) => (
            <button key={m.program.id} type="button" className="sales-result is-opened" disabled={elegir.isPending}
              onClick={() => elegir.mutate({ p: m.program.id, z: m.zones.length === 1 ? m.zones[0].id : undefined })}>
              <strong>{m.program.name}</strong><small>{m.zones.map((z) => z.name).join(" · ") || "Sin zonas"}</small>
            </button>
          ))}
        </div>
      </article>
    </div>
  );
}

/** Campos que maneja la tarjeta de términos y firma, no el formulario. */
const AUTH_TYPES = new Set(["terms_checkbox", "signature", "system_datetime"]);
const isAuthField = (f: { key: string; type: string }) => AUTH_TYPES.has(f.type) || f.key === "authorization.customer_name";

export function SignatureImage({ caseId, version }: { caseId: string; version: string }) {
  const [url, setUrl] = useState<string | null>(null);
  useEffect(() => {
    let vivo = true;
    let obj: string | null = null;
    apiClient.get(`/cases/${caseId}/terms-acceptance/signature`, { responseType: "blob" })
      .then((r) => { obj = URL.createObjectURL(r.data); if (vivo) setUrl(obj); }).catch(() => undefined);
    return () => { vivo = false; if (obj) URL.revokeObjectURL(obj); };
  }, [caseId, version]);
  return url ? <img src={url} alt="Firma del cliente" className="sales-signed-img" /> : <div className="sales-signed-img is-loading" />;
}

/**
 * Términos y firma. La firma dibujada se guarda con «Guardar y seguir» del
 * formulario (no hay un botón «Firmar» aparte: dibujar y pasar al siguiente
 * paso sin tocarlo dejaba el paso sin firma). `registerPending` le entrega al
 * formulario la acción de firmar mientras haya una firma dibujada sin guardar.
 */
function TermsAndSignature({ caseId, terms, acceptance, editable, defaultName, coords, onSigned, onError, registerPending }: {
  caseId: string; terms: { title: string; body: string; version: string; language: string };
  acceptance: { customer_name: string; accepted_at: string } | null; editable: boolean; defaultName: string;
  coords: { latitude: number; longitude: number } | null; onSigned: () => void; onError: (m: string | null) => void;
  registerPending: (firmar: (() => Promise<unknown>) | null) => void;
}) {
  const [nombre, setNombre] = useState(acceptance?.customer_name ?? defaultName);
  const [leido, setLeido] = useState(false);
  const [repitiendo, setRepitiendo] = useState(false);
  const firmar = useMutation({
    mutationFn: (signature: string) => acceptTerms(caseId, { customer_name: nombre, signature, ...(coords ?? {}) }),
    onSuccess: () => { onError(null); setRepitiendo(false); setLeido(false); onSigned(); },
    onError: (e) => onError(apiErrorMessage(e)),
  });
  const firmado = Boolean(acceptance) && !repitiendo;
  const listo = leido && nombre.trim().length >= 3;
  const [dibujo, setDibujo] = useState<string | null>(null);
  useEffect(() => {
    registerPending(listo && dibujo && !firmado ? () => firmar.mutateAsync(dibujo) : null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [listo, dibujo, firmado, nombre]);
  useEffect(() => () => registerPending(null), [registerPending]);
  return (
    <section className={`sales-terms${firmado ? " is-signed" : ""}`}>
      <h2>{terms.title}</h2>
      <div className="sales-terms-body"><p>{terms.body}</p><small>Versión {terms.version} · {terms.language === "es" ? "español" : "inglés"}</small></div>
      {firmado && acceptance ? (
        <div className="sales-signed">
          <SignatureImage caseId={caseId} version={acceptance.accepted_at} />
          <div>
            <strong>✓ Aceptó y firmó {acceptance.customer_name}</strong>
            <span>{new Date(acceptance.accepted_at).toLocaleString("es-CO", { dateStyle: "long", timeStyle: "short" })}</span>
            <span>Términos versión {terms.version}</span>
            {editable && <button type="button" className="acta-btn is-quiet" onClick={() => setRepitiendo(true)}>Repetir la firma</button>}
          </div>
        </div>
      ) : editable ? (
        <>
          <label className={`form-choice is-terms${leido ? " is-on" : ""}`}>
            <input type="checkbox" checked={leido} onChange={(e) => setLeido(e.target.checked)} /> El cliente leyó y acepta la autorización
          </label>
          <div className="form-field"><label className="form-label" htmlFor="firma-nombre">Nombre de quien firma</label>
            <input id="firma-nombre" value={nombre} onChange={(e) => setNombre(e.target.value)} /></div>
          {listo ? (
            <div className="sales-sign"><p className="form-label">Firma del cliente</p>
              <SignaturePad onCapture={(png) => firmar.mutate(png)} onDraw={setDibujo} hideCapture disabled={firmar.isPending} />
              <small className="form-help">La firma se guarda al tocar «Guardar y seguir».</small></div>
          ) : <p className="acta-empty">Marca la aceptación y escribe el nombre para habilitar la firma.</p>}
          {repitiendo && <button type="button" className="acta-btn is-quiet" onClick={() => setRepitiendo(false)}>Cancelar, dejar la firma anterior</button>}
        </>
      ) : <p className="acta-empty">El cliente todavía no ha firmado.</p>}
    </section>
  );
}

function Review({ caseId, evaluation: evaluada, unsaved, editable, resubmit, onGo, onSent, onError }: {
  caseId: string; evaluation: Evaluation; unsaved: Set<string>; editable: boolean; resubmit: boolean;
  onGo: (step: string) => void; onSent: () => void; onError: (m: string | null) => void;
}) {
  const { hasPermission } = useAuth();
  const enviar = useMutation({ mutationFn: () => submitCase(caseId), onSuccess: () => { onError(null); onSent(); },
    onError: (e) => onError(apiErrorMessage(e)) });
  // Un paso con cambios sin guardar no cuenta como completo: el envío lo valida
  // el servidor con lo guardado.
  const evaluation = { ...evaluada, can_submit: evaluada.can_submit && unsaved.size === 0,
    steps: evaluada.steps.map((s) => ({ ...s, complete: s.complete && !unsaved.has(s.code) })) };
  const porPaso = evaluation.steps.map((s) => ({ ...s, faltan: evaluation.missing.filter((m) => m.step === s.code) }));
  return (
    <section className="sales-review">
      <h2>{!editable ? "Enviado a revisión" : evaluation.can_submit ? "Todo listo para enviar" : evaluation.missing.length ? `Faltan ${evaluation.missing.length} para enviar` : "Hay pasos sin guardar"}</h2>
      {!editable && <p className="acta-lead">Administración lo está revisando. Si hay algo que corregir, te lo devuelve con el motivo y vuelve a aparecer en «Mi día».</p>}
      <ul className="billing-req">
        {porPaso.map((s) => (
          <li key={s.code} className={s.complete ? "is-met" : undefined}>
            <span className="acta-tick" aria-hidden="true">{s.complete ? "✓" : ""}</span>
            <span className="billing-req-label">{s.title}
              {unsaved.has(s.code) && <small>Tiene cambios sin guardar: ábrelo y toca «Guardar y seguir»</small>}
              {s.faltan.length > 0 && <small>Falta: {s.faltan.map((m) => m.label).join(", ")}</small>}
              {Object.keys(evaluation.errors).some((k) => s.fields.some((f) => f.key === k)) && <small>Hay valores por corregir</small>}
            </span>
            {!s.complete && <button type="button" className="acta-btn is-line" onClick={() => onGo(s.code)}>Completar</button>}
          </li>
        ))}
      </ul>
      {editable && hasPermission("cases.submit") && (
        <button type="button" className="acta-btn is-primary sales-submit" disabled={!evaluation.can_submit || enviar.isPending}
          onClick={() => enviar.mutate()}>{enviar.isPending ? "Enviando…" : resubmit ? "Reenviar a revisión" : "Enviar a revisión"}</button>
      )}
    </section>
  );
}
