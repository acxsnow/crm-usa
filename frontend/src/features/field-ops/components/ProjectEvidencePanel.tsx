import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { deleteEvidence, fetchEvidenceObjectUrl, listProjectEvidencePage, uploadEvidence } from "../api";
import { apiErrorMessage, useFieldCatalogs } from "../module5Api";
import { confirmAction } from "@/components/ui/ConfirmDialog";
import { useAuth } from "@/features/auth/AuthContext";
import { CameraIcon, ClockIcon, PinIcon, VideoIcon } from "./icons";
import { PaginationControls } from "@/components/PaginationControls";
import { type Evidence, type EvidenceCategory } from "@/types/fieldOps";

const EVIDENCE_PAGE_SIZE = 12;

function EvidenceViewer({ evidence, onClose, onDeleted }: {
  evidence: Evidence; onClose: () => void; onDeleted: () => void;
}) {
  const { data: categoryLabels } = useFieldCatalogs();
  // D-014: quitar una evidencia es de `evidence.delete` (Administrador).
  const puedeQuitar = useAuth().hasPermission("evidence.delete");
  const [errorQuitar, setErrorQuitar] = useState<string | null>(null);
  const quitar = useMutation({
    mutationFn: () => deleteEvidence(evidence.id),
    onSuccess: onDeleted,
    onError: (err) => setErrorQuitar(apiErrorMessage(err)),
    meta: { successMessage: "Evidencia quitada." },
  });
  const [url, setUrl] = useState<string | null>(null);
  const [zoom, setZoom] = useState(1);
  const isVideo = evidence.mime_type?.startsWith("video/");

  useEffect(() => {
    let active = true;
    fetchEvidenceObjectUrl(evidence.id).then((value) => { if (active) setUrl(value); }).catch(() => undefined);
    const closeOnEscape = (event: KeyboardEvent) => { if (event.key === "Escape") onClose(); };
    window.addEventListener("keydown", closeOnEscape);
    return () => {
      active = false;
      window.removeEventListener("keydown", closeOnEscape);
    };
  }, [evidence.id, onClose]);

  return (
    <div
      className="evidence-viewer-backdrop"
      role="dialog"
      aria-modal="true"
      aria-label="Vista ampliada de evidencia"
      onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}
    >
      <div className="evidence-viewer">
        <header className="evidence-viewer-header">
          <div>
            <strong>{evidence.original_filename ?? "Evidencia"}</strong>
            <small>
              {categoryLabels?.evidence_categories[evidence.category] ?? evidence.category}
              {" · "}
              {evidence.watermarked ? "Marca visible aplicada" : "Sin marca"}
            </small>
          </div>
          <button type="button" className="evidence-viewer-close" onClick={onClose} aria-label="Cerrar vista ampliada">×</button>
        </header>
        <div className="evidence-viewer-stage">
          {url ? (
            isVideo
              ? <video controls autoPlay preload="metadata" src={url} />
              : <img src={url} alt={evidence.original_filename ?? "Evidencia ampliada"} style={{ transform: `scale(${zoom})` }} />
          ) : (
            <div className="evidence-placeholder">Cargando evidencia...</div>
          )}
        </div>
        <footer className="evidence-viewer-footer">
          {!isVideo && (
            <div className="evidence-zoom-controls">
              <button type="button" onClick={() => setZoom((value) => Math.max(1, value - 0.25))}>−</button>
              <span>{Math.round(zoom * 100)}%</span>
              <button type="button" onClick={() => setZoom((value) => Math.min(3, value + 0.25))}>+</button>
              <button type="button" onClick={() => setZoom(1)}>Restablecer</button>
            </div>
          )}
          {puedeQuitar && (
            <button type="button" className="acta-btn is-quiet" disabled={quitar.isPending}
              onClick={async () => {
                setErrorQuitar(null);
                const ok = await confirmAction({
                  title: "¿Quitar esta evidencia?",
                  message: "Deja de verse en la obra y en el acta. Si era la única foto de un renglón del checklist que "
                    + "la exige, el renglón vuelve a pendiente.",
                  confirmLabel: "Quitar", cancelLabel: "Dejarla",
                });
                if (ok) quitar.mutate();
              }}>Quitar evidencia</button>
          )}
          {errorQuitar && <p className="form-error" role="alert">{errorQuitar}</p>}
          <div className="evidence-watermark-detail">
            <strong>Marca de evidencia</strong>
            <span>{evidence.latitude != null && evidence.longitude != null ? `GPS: ${evidence.latitude.toFixed(6)}, ${evidence.longitude.toFixed(6)}` : "GPS: no disponible"}</span>
            <span>{evidence.captured_at ? `Fecha: ${new Date(evidence.captured_at).toLocaleString("es-CO")}` : "Fecha: no disponible"}</span>
          </div>
        </footer>
      </div>
    </div>
  );
}

function EvidenceCard({ evidence, onOpen }: { evidence: Evidence; onOpen: (evidence: Evidence) => void }) {
  const { data: categoryLabels } = useFieldCatalogs();
  const [url, setUrl] = useState<string | null>(null);
  const isVideo = evidence.mime_type?.startsWith("video/");

  useEffect(() => {
    let active = true;
    fetchEvidenceObjectUrl(evidence.id).then((value) => { if (active) setUrl(value); }).catch(() => undefined);
    return () => { active = false; };
  }, [evidence.id]);

  const categoria = categoryLabels?.evidence_categories[evidence.category] ?? evidence.category;
  const cuando = evidence.captured_at ?? evidence.created_at;

  return (
    <figure className="annex-thumb">
      <button type="button" className="annex-thumb-img" onClick={() => onOpen(evidence)} aria-label={`Ver ${categoria} en detalle`}>
        {url ? (isVideo ? <video muted preload="metadata" src={url} /> : <img src={url} alt={categoria} />) : <span className="annex-thumb-loading">Cargando…</span>}
        {isVideo && <span className="annex-thumb-play" aria-hidden="true">▶</span>}
      </button>
      <figcaption>
        <strong>{categoria}</strong>
        <span><ClockIcon size={11} /> {new Date(cuando).toLocaleString("es-CO", { day: "2-digit", month: "2-digit", year: "2-digit", hour: "2-digit", minute: "2-digit", hourCycle: "h23" })}</span>
        <span><PinIcon size={11} /> {evidence.latitude != null && evidence.longitude != null ? `${evidence.latitude.toFixed(4)}, ${evidence.longitude.toFixed(4)}` : "Sin GPS"}</span>
      </figcaption>
    </figure>
  );
}

interface ProjectEvidencePanelProps {
  projectId: string;
  canUpload: boolean;
  geoStatus: "idle" | "requesting" | "granted" | "denied";
  coords: { latitude: number; longitude: number } | null;
}

export function ProjectEvidencePanel({ projectId, canUpload, geoStatus, coords }: ProjectEvidencePanelProps) {
  const queryClient = useQueryClient();
  const { data: catalogs } = useFieldCatalogs();
  const [evidencePage, setEvidencePage] = useState(1);
  const [selectedEvidence, setSelectedEvidence] = useState<Evidence | null>(null);
  const [category, setCategory] = useState<EvidenceCategory>("additional_photo");
  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);

  const { data: evidenceData } = useQuery({
    queryKey: ["project-evidence", projectId, evidencePage],
    queryFn: () => listProjectEvidencePage(projectId, evidencePage, EVIDENCE_PAGE_SIZE),
  });
  const evidence = evidenceData?.items ?? [];

  const uploadMutation = useMutation({
    mutationFn: () => uploadEvidence(projectId, file!, { category, latitude: coords?.latitude, longitude: coords?.longitude }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["project-evidence", projectId], exact: false });
      setFile(null);
    },
  });

  return (
    <section className="annex-section" aria-labelledby="anexo-evidencias">
      <div className="annex-section-head">
        <h3 id="anexo-evidencias">Evidencias</h3>
        <span className="annex-count">{evidenceData?.total ?? 0} archivos</span>
      </div>
      <p className="acta-lead">Las fotos del checklist se toman desde su línea; aquí van las adicionales.</p>

      {canUpload && (
        <form
          className="annex-evidence"
          onSubmit={(e) => {
            e.preventDefault();
            if (file) uploadMutation.mutate();
          }}
        >
          <label
            className={`annex-drop ${dragging ? "is-over" : ""} ${file ? "has-file" : ""}`}
            onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragging(false);
              const dropped = e.dataTransfer.files?.[0];
              if (dropped) setFile(dropped);
            }}
          >
            <input
              type="file"
              hidden
              accept="image/*,video/mp4,video/quicktime,video/webm"
              capture="environment"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
            <strong>{file ? file.name : "Arrastra y suelta o toca para subir"}</strong>
            <span className="annex-drop-icons"><CameraIcon size={26} /> <span>o</span> <VideoIcon size={26} /></span>
          </label>

          <div className="annex-evidence-controls">
            <label htmlFor="evidencia-categoria" className="visually-hidden">Categoría</label>
            <select id="evidencia-categoria" value={category} onChange={(e) => setCategory(e.target.value)}>
              {Object.entries(catalogs?.evidence_categories ?? {}).map(([code, label]) => (
                <option key={code} value={code}>{label}</option>
              ))}
            </select>
            <button type="submit" className="acta-btn is-primary" disabled={!file || uploadMutation.isPending}>
              {uploadMutation.isPending ? "Subiendo…" : "Subir evidencia"}
            </button>
          </div>
        </form>
      )}

      <p className="annex-note">
        <PinIcon size={14} />{" "}
        {geoStatus === "denied"
          ? "Ubicación no concedida: los archivos quedarán marcados «sin GPS»."
          : "Ubicación GPS y hora grabadas automáticamente en cada archivo."}
      </p>

      <div className="annex-thumbs">
        {evidence.length > 0
          ? evidence.map((ev) => <EvidenceCard key={ev.id} evidence={ev} onOpen={setSelectedEvidence} />)
          : <p className="acta-empty">Todavía no hay evidencias.</p>}
      </div>

      {selectedEvidence && (
        <EvidenceViewer evidence={selectedEvidence} onClose={() => setSelectedEvidence(null)}
          onDeleted={() => {
            setSelectedEvidence(null);
            queryClient.invalidateQueries({ queryKey: ["project-evidence", projectId], exact: false });
            queryClient.invalidateQueries({ queryKey: ["project-checklist", projectId], exact: false });
          }} />
      )}
      {evidenceData && evidenceData.total > EVIDENCE_PAGE_SIZE && (
        <PaginationControls page={evidencePage} pageSize={EVIDENCE_PAGE_SIZE} total={evidenceData.total} onPageChange={setEvidencePage} />
      )}
    </section>
  );
}
