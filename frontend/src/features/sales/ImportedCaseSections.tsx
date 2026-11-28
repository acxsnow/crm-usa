import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";

import { PaginationControls } from "@/components/PaginationControls";
import { listPrograms } from "@/features/programs/api";
import { apiErrorMessage } from "@/features/field-ops/module5Api";
import { usePaginatedQuery } from "@/lib/usePaginatedQuery";
import {
  thumbBlobUrl,
  importedKeys,
  openCaseFile,
  setImportedProgram,
  type ImportedFile,
  type ImportedNote,
} from "./api";

const PAGINA_ARCHIVOS = 12;
const PAGINA_NOTAS = 10;

const NOTA: Record<ImportedNote["kind"], string> = {
  notepad: "Bloc de notas", comment: "Comentario", checklist: "Lista de verificación",
};

function fecha(iso: string) {
  return new Date(iso).toLocaleString("es-US", {
    day: "numeric", month: "short", year: "numeric", hour: "numeric", minute: "2-digit",
  });
}

/** Etiqueta que marca un expediente traído de CompanyCam. */
export function ImportedBadge() {
  return <span className="billing-chip is-withdrawn">Importado de CompanyCam</span>;
}

/**
 * Programa de un expediente importado. Administración lo elige aquí (el
 * expediente sigue «En espera» o «Cerrado»; solo se le asigna el programa).
 */
export function ImportedProgram({ caseId, programId, canEdit, onDone }: {
  caseId: string; programId: string | null; canEdit: boolean; onDone: () => void;
}) {
  const { data: programas } = useQuery({ queryKey: ["board-programs"], queryFn: listPrograms, staleTime: 5 * 60 * 1000, enabled: canEdit });
  const [elegido, setElegido] = useState(programId ?? "");
  const [error, setError] = useState<string | null>(null);
  const guardar = useMutation({
    mutationFn: () => setImportedProgram(caseId, elegido),
    onSuccess: () => { setError(null); onDone(); },
    onError: (e) => setError(apiErrorMessage(e)),
  });
  if (!canEdit) return null;
  return (
    <section className="review-section imp-program" aria-labelledby="imp-program">
      <h2 id="imp-program">Programa</h2>
      <p className="acta-note">Este expediente viene de CompanyCam. Elige a qué programa pertenece; no cambia su etapa.</p>
      <div className="imp-program-row">
        <select aria-label="Programa" value={elegido} onChange={(e) => setElegido(e.target.value)}>
          <option value="">Sin programa</option>
          {(programas ?? []).filter((p) => p.active || p.id === programId).map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>
        <button type="button" className="acta-btn is-primary" disabled={!elegido || elegido === programId || guardar.isPending}
          onClick={() => guardar.mutate()}>
          {guardar.isPending ? "Guardando…" : "Guardar programa"}
        </button>
      </div>
      {error && <p className="form-error-text" role="alert">{error}</p>}
    </section>
  );
}

/** Miniatura que solo se pide cuando entra en pantalla (cientos de fotos por expediente). */
function MiniaturaPerezosa({ file }: { file: ImportedFile }) {
  const esImagen = (file.mime_type ?? "").startsWith("image/");
  const caja = useRef<HTMLButtonElement>(null);
  const [url, setUrl] = useState<string | null>(null);
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    if (!esImagen || !caja.current) return;
    const obs = new IntersectionObserver((es) => { if (es.some((x) => x.isIntersecting)) { setVisible(true); obs.disconnect(); } },
      { rootMargin: "200px" });
    obs.observe(caja.current);
    return () => obs.disconnect();
  }, [esImagen]);
  useEffect(() => {
    if (!visible) return;
    let vivo = true;
    let obj: string | null = null;
    thumbBlobUrl(file.id).then((u) => { obj = u; if (vivo) setUrl(u); }).catch(() => undefined);
    return () => { vivo = false; if (obj) URL.revokeObjectURL(obj); };
  }, [visible, file.id]);
  return (
    <button ref={caja} type="button" className="imp-thumb" onClick={() => openCaseFile(file.id)}
      aria-label={`Ver ${file.label ?? file.original_filename ?? "archivo"}`}>
      {esImagen ? (url ? <img src={url} alt="" loading="lazy" /> : <span className="is-loading" />)
        : <span>{file.mime_type === "application/pdf" ? "PDF" : "Archivo"}</span>}
    </button>
  );
}

/** Fotos y documentos importados, en cuadrícula paginada de 12. */
export function ImportedFiles({ caseId }: { caseId: string }) {
  const lista = usePaginatedQuery<ImportedFile>({
    key: importedKeys.files(caseId), path: `/cases/${caseId}/imported-files`, pageSize: PAGINA_ARCHIVOS,
  });
  return (
    <section className="review-section" aria-labelledby="imp-files">
      <div className="review-section-head">
        <h2 id="imp-files">Fotos y documentos de CompanyCam</h2>
        <span className="review-tally"><span className="billing-chip is-preparing">{lista.total} en total</span></span>
      </div>
      {!lista.isLoading && lista.total === 0 && <p className="acta-empty">Todavía no hay fotos ni documentos descargados.</p>}
      <ul className="imp-grid">
        {lista.items.map((f) => (
          <li key={f.id} className="imp-card">
            <MiniaturaPerezosa file={f} />
            <div className="imp-card-body">
              <strong>{f.label ?? f.original_filename ?? (f.kind === "photo" ? "Foto" : "Documento")}</strong>
              {f.author_name && <small>{f.author_name}</small>}
              {f.captured_at && <small>{fecha(f.captured_at)}</small>}
              {f.latitude != null && f.longitude != null && <small>{f.latitude.toFixed(4)}, {f.longitude.toFixed(4)}</small>}
              {f.tags.length > 0 && <span className="imp-tags">{f.tags.map((t) => <span key={t} className="billing-chip is-withdrawn">{t}</span>)}</span>}
              <button type="button" className="acta-btn is-line" onClick={() => openCaseFile(f.id)}>Ver</button>
            </div>
          </li>
        ))}
      </ul>
      <PaginationControls {...lista.controls} />
    </section>
  );
}

/** Bloc de notas, comentarios y listas de CompanyCam. */
export function ImportedNotes({ caseId }: { caseId: string }) {
  const lista = usePaginatedQuery<ImportedNote>({
    key: importedKeys.notes(caseId), path: `/cases/${caseId}/notes`, pageSize: PAGINA_NOTAS,
  });
  return (
    <section className="review-section" aria-labelledby="imp-notes">
      <h2 id="imp-notes">Notas de CompanyCam</h2>
      {!lista.isLoading && lista.total === 0 && <p className="acta-empty">Sin notas.</p>}
      <ul className="imp-notes">
        {lista.items.map((n) => (
          <li key={n.id} className="imp-note">
            <div className="imp-note-head">
              <span className="billing-chip is-withdrawn">{NOTA[n.kind]}</span>
              <small>{[n.author_name, n.occurred_at ? fecha(n.occurred_at) : null].filter(Boolean).join(" · ")}</small>
            </div>
            <p className="imp-note-body">{n.body}</p>
          </li>
        ))}
      </ul>
      <PaginationControls {...lista.controls} />
    </section>
  );
}
