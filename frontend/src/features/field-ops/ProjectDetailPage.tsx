import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createTask,
  createTaskComment,
  fetchAttestationPdfObjectUrl,
  fetchEvidenceObjectUrl,
  getAttestation,
  getProject,
  getProjectChecklist,
  listProjectEvidencePage,
  listProjectTasks,
  listTaskComments,
  signAsTechnician,
  requestCustomerSignature,
  updateTask,
  uploadEvidence,
} from "./api";
import { listUsers } from "@/features/users/api";
import { SignaturePad } from "./SignaturePad";
import { PaginationControls } from "@/components/PaginationControls";
import type { Evidence, EvidenceCategory, FieldTask, TaskStatus } from "@/types/fieldOps";
import { useAuth } from "@/features/auth/AuthContext";
import { useFieldCatalogs } from "./module5Api";
import { ChecklistPanel } from "./components/ChecklistPanel";
import { ConditionsPanel } from "./components/ConditionsPanel";
import { EquipmentPanel } from "./components/EquipmentPanel";
import { InspectionsPanel } from "./components/InspectionsPanel";
import { InstallationPanel } from "./components/InstallationPanel";
import { MaterialsPanel } from "./components/MaterialsPanel";
import { PermitsPanel } from "./components/PermitsPanel";

const EVIDENCE_PAGE_SIZE = 12;

const TASK_COLUMNS: { status: TaskStatus; label: string }[] = [
  { status: "pending", label: "Pendiente" },
  { status: "in_progress", label: "En progreso" },
  { status: "done", label: "Completada" },
];

function EvidenceViewer({ evidence, onClose }: { evidence: Evidence; onClose: () => void }) {
  const { data: categoryLabels } = useFieldCatalogs();
  const [url, setUrl] = useState<string | null>(null);
  const [zoom, setZoom] = useState(1);
  const isVideo = evidence.mime_type?.startsWith("video/");

  useEffect(() => {
    let active = true;
    fetchEvidenceObjectUrl(evidence.id).then((value) => { if (active) setUrl(value); }).catch(() => undefined);
    const closeOnEscape = (event: KeyboardEvent) => { if (event.key === "Escape") onClose(); };
    window.addEventListener("keydown", closeOnEscape);
    return () => { active = false; window.removeEventListener("keydown", closeOnEscape); };
  }, [evidence.id, onClose]);

  return <div className="evidence-viewer-backdrop" role="dialog" aria-modal="true" aria-label="Vista ampliada de evidencia" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
    <div className="evidence-viewer">
      <header className="evidence-viewer-header">
        <div><strong>{evidence.original_filename ?? "Evidencia"}</strong><small>{categoryLabels?.evidence_categories[evidence.category] ?? evidence.category} · {evidence.watermarked ? "Marca visible aplicada" : "Sin marca"}</small></div>
        <button type="button" className="evidence-viewer-close" onClick={onClose} aria-label="Cerrar vista ampliada">×</button>
      </header>
      <div className="evidence-viewer-stage">
        {url ? (isVideo
          ? <video controls autoPlay preload="metadata" src={url} />
          : <img src={url} alt={evidence.original_filename ?? "Evidencia ampliada"} style={{ transform: `scale(${zoom})` }} />)
          : <div className="evidence-placeholder">Cargando evidencia...</div>}
      </div>
      <footer className="evidence-viewer-footer">
        {!isVideo && <div className="evidence-zoom-controls"><button type="button" onClick={() => setZoom((value) => Math.max(1, value - 0.25))}>−</button><span>{Math.round(zoom * 100)}%</span><button type="button" onClick={() => setZoom((value) => Math.min(3, value + 0.25))}>+</button><button type="button" onClick={() => setZoom(1)}>Restablecer</button></div>}
        <div className="evidence-watermark-detail"><strong>Marca de evidencia</strong><span>{evidence.latitude != null && evidence.longitude != null ? `GPS: ${evidence.latitude.toFixed(6)}, ${evidence.longitude.toFixed(6)}` : "GPS: no disponible"}</span><span>{evidence.captured_at ? `Fecha: ${new Date(evidence.captured_at).toLocaleString("es-CO")}` : "Fecha: no disponible"}</span></div>
      </footer>
    </div>
  </div>;
}

function EvidenceCard({ evidence, onOpen }: { evidence: Evidence; onOpen: (evidence: Evidence) => void }) {
  const { data: categoryLabels } = useFieldCatalogs();
  const [url, setUrl] = useState<string | null>(null);
  useEffect(() => { let active = true; fetchEvidenceObjectUrl(evidence.id).then((value) => { if (active) setUrl(value); }).catch(() => undefined); return () => { active = false; }; }, [evidence.id]);
  const isVideo = evidence.mime_type?.startsWith("video/");
  return <article className="evidence-card"><button type="button" className="evidence-preview-button" onClick={() => onOpen(evidence)} aria-label={`Abrir ${evidence.original_filename ?? "evidencia"}`}>{url ? (isVideo ? <video muted preload="metadata" src={url} /> : <img src={url} alt={evidence.original_filename ?? "Evidencia"} />) : <div className="evidence-placeholder">Cargando vista previa...</div>}<span className="evidence-open-hint">Ver en detalle ↗</span></button><div className="evidence-card-info"><strong>{evidence.original_filename ?? "Evidencia"}</strong><span>{categoryLabels?.evidence_categories[evidence.category] ?? evidence.category} · {evidence.watermarked ? "Marca visible ✓" : "Sin marca"}</span><small>{evidence.latitude != null && evidence.longitude != null ? `GPS ${evidence.latitude.toFixed(5)}, ${evidence.longitude.toFixed(5)}` : "GPS no disponible"}</small><small>{evidence.captured_at ? new Date(evidence.captured_at).toLocaleString("es-CO") : "Fecha no disponible"}</small></div></article>;
}

function TaskComments({ taskId }: { taskId: string }) {
  const queryClient = useQueryClient();
  const { data: comments } = useQuery({ queryKey: ["task-comments", taskId], queryFn: () => listTaskComments(taskId) });
  const [body, setBody] = useState("");

  const addMutation = useMutation({
    mutationFn: () => createTaskComment(taskId, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["task-comments", taskId] });
      setBody("");
    },
  });

  return (
    <div style={{ marginTop: "0.4rem", borderTop: "1px solid #f3f4f6", paddingTop: "0.4rem" }}>
      <ul className="plain-list">
        {(comments ?? []).map((c) => (
          <li key={c.id} style={{ fontSize: "0.78rem" }}>
            {c.body}
            <div className="pipeline-card-meta">{new Date(c.created_at).toLocaleString()}</div>
          </li>
        ))}
        {(comments ?? []).length === 0 && <li className="page-subtitle">Sin comentarios.</li>}
      </ul>
      <form
        className="inline-form"
        style={{ marginTop: "0.25rem" }}
        onSubmit={(e) => {
          e.preventDefault();
          if (body.trim()) addMutation.mutate();
        }}
      >
        <input
          placeholder="Agregar comentario"
          value={body}
          onChange={(e) => setBody(e.target.value)}
          style={{ fontSize: "0.8rem" }}
        />
        <button type="submit" disabled={addMutation.isPending}>
          Comentar
        </button>
      </form>
    </div>
  );
}

function TaskBoard({ projectId }: { projectId: string }) {
  const queryClient = useQueryClient();
  const { data: tasks } = useQuery({ queryKey: ["project-tasks", projectId], queryFn: () => listProjectTasks(projectId) });
  // Best-effort: only users with users.manage see the assignee dropdown
  // populated with real names; everyone else can still create/move tasks,
  // just without a name-based picker.
  const { data: users } = useQuery({ queryKey: ["users"], queryFn: listUsers, retry: false, throwOnError: false });

  const [title, setTitle] = useState("");
  const [assignedUserId, setAssignedUserId] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [expandedTaskId, setExpandedTaskId] = useState<string | null>(null);

  const createMutation = useMutation({
    mutationFn: () =>
      createTask(projectId, {
        title,
        assigned_user_id: assignedUserId || undefined,
        due_date: dueDate ? new Date(dueDate).toISOString() : undefined,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["project-tasks", projectId] });
      setTitle("");
      setAssignedUserId("");
      setDueDate("");
    },
  });

  const moveMutation = useMutation({
    mutationFn: ({ taskId, status }: { taskId: string; status: TaskStatus }) => updateTask(taskId, { status }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["project-tasks", projectId] }),
  });

  const assigneeName = (userId?: string | null) => {
    if (!userId) return "Sin asignar";
    const match = users?.items.find((u) => u.id === userId);
    return match ? match.full_name : "Asignado";
  };

  return (
    <div>
      <h3>Tablero de tareas</h3>
      <form
        className="inline-form"
        onSubmit={(e) => {
          e.preventDefault();
          if (title.trim()) createMutation.mutate();
        }}
      >
        <input placeholder="Nueva tarea" value={title} onChange={(e) => setTitle(e.target.value)} required />
        <select value={assignedUserId} onChange={(e) => setAssignedUserId(e.target.value)}>
          <option value="">Sin asignar</option>
          {(users?.items ?? []).map((u) => (
            <option key={u.id} value={u.id}>
              {u.full_name}
            </option>
          ))}
        </select>
        <input type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} />
        <button type="submit" disabled={createMutation.isPending}>
          Agregar tarea
        </button>
      </form>

      <div className="pipeline-board">
        {TASK_COLUMNS.map((column) => (
          <div key={column.status} className="pipeline-column">
            <h3>
              {column.label} <span className="pipeline-count">{(tasks ?? []).filter((t) => t.status === column.status).length}</span>
            </h3>
            {(tasks ?? [])
              .filter((t) => t.status === column.status)
              .map((task: FieldTask) => (
                <div key={task.id} className="pipeline-card">
                  <div>
                    {task.title}
                    {task.is_overdue && (
                      <span className="status-pill status-inactive" style={{ marginLeft: "0.4rem" }}>
                        vencida
                      </span>
                    )}
                  </div>
                  <div className="pipeline-card-meta">
                    {assigneeName(task.assigned_user_id)}
                    {task.due_date ? ` · vence ${new Date(task.due_date).toLocaleDateString()}` : ""}
                  </div>
                  <select
                    value={task.status}
                    onChange={(e) => moveMutation.mutate({ taskId: task.id, status: e.target.value as TaskStatus })}
                  >
                    {TASK_COLUMNS.map((c) => (
                      <option key={c.status} value={c.status}>
                        {c.label}
                      </option>
                    ))}
                  </select>
                  <button
                    type="button"
                    className="link-button"
                    style={{ marginTop: "0.3rem" }}
                    onClick={() => setExpandedTaskId(expandedTaskId === task.id ? null : task.id)}
                  >
                    {expandedTaskId === task.id ? "Ocultar comentarios" : "Comentarios"}
                  </button>
                  {expandedTaskId === task.id && <TaskComments taskId={task.id} />}
                </div>
              ))}
            {(tasks ?? []).filter((t) => t.status === column.status).length === 0 && (
              <p className="page-subtitle">Sin tareas.</p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function useGeolocation() {
  const [coords, setCoords] = useState<{ latitude: number; longitude: number } | null>(null);
  const [status, setStatus] = useState<"idle" | "requesting" | "granted" | "denied">("idle");

  const request = () => {
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
      { enableHighAccuracy: true, timeout: 10000 }
    );
  };

  return { coords, status, request };
}

export function ProjectDetailPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const queryClient = useQueryClient();
  const geo = useGeolocation();

  const { data: project, isLoading: projectLoading } = useQuery({
    queryKey: ["project", projectId],
    queryFn: () => getProject(projectId!),
    enabled: !!projectId,
  });
  const { data: checklist } = useQuery({
    queryKey: ["project-checklist", projectId],
    queryFn: () => getProjectChecklist(projectId!),
    enabled: !!projectId,
  });
  const [evidencePage, setEvidencePage] = useState(1);
  const { data: evidenceData } = useQuery({
    queryKey: ["project-evidence", projectId, evidencePage],
    queryFn: () => listProjectEvidencePage(projectId!, evidencePage, EVIDENCE_PAGE_SIZE),
    enabled: !!projectId,
  });
  const evidence = evidenceData?.items;
  const [selectedEvidence, setSelectedEvidence] = useState<Evidence | null>(null);
  const { data: attestation } = useQuery({
    queryKey: ["project-attestation", projectId],
    queryFn: () => getAttestation(projectId!),
    enabled: !!projectId,
  });

  useEffect(() => {
    geo.request();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  const { hasPermission } = useAuth();
  const { data: catalogs } = useFieldCatalogs();
  const [category, setCategory] = useState<EvidenceCategory>("additional_photo");
  const [file, setFile] = useState<File | null>(null);
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);

  const uploadMutation = useMutation({
    mutationFn: () =>
      uploadEvidence(projectId!, file!, {
        category,
        latitude: geo.coords?.latitude,
        longitude: geo.coords?.longitude,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["project-evidence", projectId], exact: false });
      setFile(null);
    },
  });

  const technicianSignMutation = useMutation({
    mutationFn: (signature: string) => signAsTechnician(projectId!, signature),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["project-attestation", projectId] }),
  });

  const requestSignatureMutation = useMutation({
    mutationFn: () => requestCustomerSignature(projectId!),
  });

  if (projectLoading || !project) return <p>Cargando...</p>;
  const cerrada = project.status === "completed";

  return (
    <div>
      <h1>{project.title}</h1>
      <p className="page-subtitle">
        {[project.address_street, project.address_unit, project.address_city].filter(Boolean).join(", ")} ·{" "}
        <span className={`status-pill status-${project.status}`}>{project.status}</span>
      </p>

      <InstallationPanel
        project={project}
        canSchedule={hasPermission("dispatch.manage")}
        canClose={hasPermission("checklists.complete")}
      />
      <ConditionsPanel project={project} canEdit={hasPermission("checklists.complete")} />
      <ChecklistPanel
        project={project}
        items={checklist ?? []}
        canEdit={hasPermission("checklists.complete")}
        coords={geo.coords}
      />
      <EquipmentPanel projectId={project.id} canManage={hasPermission("equipment.manage")} closed={cerrada} />
      <MaterialsPanel projectId={project.id} canManage={hasPermission("projects.update")} closed={cerrada} />
      <PermitsPanel projectId={project.id} canManage={hasPermission("permits.manage")} />
      <InspectionsPanel
        projectId={project.id}
        canManage={hasPermission("inspections.manage")}
        installationClosed={cerrada}
      />

      <TaskBoard projectId={project.id} />

      <h3>Evidencia</h3>
      <p className="page-subtitle">
        GPS: {geo.status === "granted" && geo.coords
          ? `${geo.coords.latitude.toFixed(5)}, ${geo.coords.longitude.toFixed(5)}`
          : geo.status === "denied"
            ? "no disponible / permiso denegado"
            : "solicitando..."}
        {" "}— la marca se incrusta sobre los píxeles del archivo: abre cualquier cuadro en “Ver en detalle” para verla en la franja inferior y comprobar GPS + fecha.
      </p>
      <form
        className="inline-form"
        onSubmit={(e) => {
          e.preventDefault();
          if (file) uploadMutation.mutate();
        }}
      >
        <select aria-label="Categoría de la evidencia" value={category} onChange={(e) => setCategory(e.target.value)}>
          {Object.entries(catalogs?.evidence_categories ?? {}).map(([code, label]) => (
            <option key={code} value={code}>{label}</option>
          ))}
        </select>
        <input type="file" accept="image/*,video/mp4,video/quicktime,video/webm" capture="environment" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        <button type="submit" disabled={!file || uploadMutation.isPending}>
          Subir
        </button>
      </form>
      <div className="evidence-gallery">{(evidence ?? []).map((ev) => <EvidenceCard key={ev.id} evidence={ev} onOpen={setSelectedEvidence} />)}</div>
      {selectedEvidence && <EvidenceViewer evidence={selectedEvidence} onClose={() => setSelectedEvidence(null)} />}
      {evidenceData && (
        <PaginationControls page={evidencePage} pageSize={EVIDENCE_PAGE_SIZE} total={evidenceData.total} onPageChange={setEvidencePage} />
      )}

      <h3>Atestación (firma digital)</h3>
      <div style={{ display: "flex", gap: "2rem", flexWrap: "wrap" }}>
        <div>
          <p><strong>Técnico</strong> {attestation?.technician_signed_at ? "— firmado ✓" : ""}</p>
          {!attestation?.technician_signed_at && (
            <SignaturePad onCapture={(sig) => technicianSignMutation.mutate(sig)} />
          )}
        </div>
        <div>
          <p><strong>Cliente</strong> {attestation?.customer_signed_at ? "— firmado ✓" : "— pendiente"}</p>
          {!attestation?.customer_signed_at && <button type="button" className="primary-button" onClick={() => requestSignatureMutation.mutate()} disabled={requestSignatureMutation.isPending}>{requestSignatureMutation.isPending ? "Enviando..." : "Enviar enlace de firma al cliente"}</button>}
          {requestSignatureMutation.data && <p className="page-subtitle">Enlace enviado a {requestSignatureMutation.data.recipient_email}. Vence el {new Date(requestSignatureMutation.data.expires_at).toLocaleDateString("es-CO")}.</p>}
          {requestSignatureMutation.isError && <p className="form-error">No se pudo enviar el enlace. Verifica que el cliente tenga correo.</p>}
        </div>
      </div>

      {attestation?.is_fully_signed && (
        <div style={{ marginTop: "1rem" }}>
          <button
            type="button"
            onClick={async () => {
              const url = await fetchAttestationPdfObjectUrl(attestation.id);
              setPdfUrl(url);
              window.open(url, "_blank");
            }}
          >
            Descargar acta firmada (PDF)
          </button>
          {pdfUrl && <span className="page-subtitle"> Listo.</span>}
        </div>
      )}
    </div>
  );
}
