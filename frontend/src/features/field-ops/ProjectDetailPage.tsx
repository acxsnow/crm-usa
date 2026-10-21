import { useEffect, useState } from "react";
import { Link, useLocation, useParams, useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createTask,
  createTaskComment,
  fetchEvidenceObjectUrl,
  getProject,
  getProjectChecklist,
  listProjectEvidencePage,
  listProjectTasks,
  listTaskComments,
  updateTask,
  uploadEvidence,
} from "./api";
import { SignaturesPanel } from "./components/SignaturesPanel";
import { PaginationControls } from "@/components/PaginationControls";
import { type Evidence, type EvidenceCategory, type FieldTask, type TaskStatus } from "@/types/fieldOps";
import { useAuth } from "@/features/auth/AuthContext";
import { useFieldCatalogs, useInstallers } from "./module5Api";
import { CameraIcon, CheckCircleIcon, CheckIcon, ClockIcon, GearIcon, PinIcon, SendIcon, VideoIcon } from "./components/icons";
import { ChecklistPanel } from "./components/ChecklistPanel";
import { ConditionsPanel } from "./components/ConditionsPanel";
import { EquipmentPanel } from "./components/EquipmentPanel";
import { InspectionsPanel } from "./components/InspectionsPanel";
import { CloseInstallationStep, ReleaseOrderStep } from "./components/InstallationPanel";
import { InstallationRecord, closeRequirements, deriveStates, openActaStep, useRecordData } from "./components/InstallationRecord";
import { MaterialsPanel } from "./components/MaterialsPanel";
import { PermitsPanel } from "./components/PermitsPanel";
import { ReviewStep } from "./components/ReviewStep";
import { BillingStep } from "./components/BillingStep";
import { ProjectBudgetPanel } from "@/features/warehouse/ProjectBudgetPanel";
import { ProjectDayLogPanel } from "@/features/warehouse/ProjectDayLogPanel";
import { hasAnyPermission } from "@/config/navigation";

const EVIDENCE_PAGE_SIZE = 12;


const COLUMN_ICON: Record<TaskStatus, JSX.Element> = {
  pending: <ClockIcon size={17} />,
  in_progress: <GearIcon size={17} />,
  done: <CheckCircleIcon size={17} />,
};

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
      {/* La foto ya trae la marca grabada en los píxeles; repetirla encima la
          tapaba. Aquí va como dato legible. */}
      <figcaption>
        <strong>{categoria}</strong>
        <span><ClockIcon size={11} /> {new Date(cuando).toLocaleString("es-CO", { day: "2-digit", month: "2-digit", year: "2-digit", hour: "2-digit", minute: "2-digit", hourCycle: "h23" })}</span>
        <span><PinIcon size={11} /> {evidence.latitude != null && evidence.longitude != null ? `${evidence.latitude.toFixed(4)}, ${evidence.longitude.toFixed(4)}` : "Sin GPS"}</span>
      </figcaption>
    </figure>
  );
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
  // Responsables posibles: quien puede instalar. El listado general de
  // usuarios exige `users.manage`, que Administración no tiene.
  const { hasPermission } = useAuth();
  const { data: installers } = useInstallers(hasPermission("dispatch.manage"));

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
    const match = installers?.find((u) => u.id === userId);
    return match ? match.full_name : "Asignado";
  };

  return (
    <section className="annex-section" aria-labelledby="anexo-tareas">
      <div className="annex-section-head">
        <h3 id="anexo-tareas">Tareas internas</h3>
        <span className="annex-count">{(tasks ?? []).length} en total</span>
      </div>
      <form
        className="panel-form annex-task-form"
        onSubmit={(e) => {
          e.preventDefault();
          if (title.trim()) createMutation.mutate();
        }}
      >
        <div className="field annex-task-title">
          <label htmlFor="tarea-titulo">Tarea</label>
          <input id="tarea-titulo" placeholder="Llevar soporte antivibración" value={title}
            onChange={(e) => setTitle(e.target.value)} required />
        </div>
        <div className="field">
          <label htmlFor="tarea-responsable">Responsable</label>
          <select id="tarea-responsable" value={assignedUserId} onChange={(e) => setAssignedUserId(e.target.value)}>
            <option value="">Sin asignar</option>
            {(installers ?? []).map((u) => (
              <option key={u.id} value={u.id}>{u.full_name}</option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="tarea-vence">Vence</label>
          <input id="tarea-vence" type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} />
        </div>
        <button type="submit" className="acta-btn is-primary" disabled={createMutation.isPending}>
          Agregar tarea
        </button>
      </form>

      <div className="annex-board">
        {TASK_COLUMNS.map((column) => {
          const enColumna = (tasks ?? []).filter((t) => t.status === column.status);
          return (
            <div key={column.status} className={`annex-column is-${column.status}`}>
              <h4>
                <span className="annex-column-title">{COLUMN_ICON[column.status]} {column.label}</span>
                <span className="annex-count">{enColumna.length}</span>
              </h4>
              <ul className="annex-task-list">
                {enColumna.map((task: FieldTask) => {
                  const hecha = task.status === "done";
                  return (
                    <li key={task.id} className="annex-task">
                      <div className="annex-task-row">
                        {hecha ? (
                          <span className="annex-task-done" aria-hidden="true"><CheckIcon size={16} strokeWidth={2.4} /></span>
                        ) : (
                          <input
                            type="checkbox"
                            className="annex-task-check"
                            aria-label={`Marcar «${task.title}» como completada`}
                            onChange={() => moveMutation.mutate({ taskId: task.id, status: "done" })}
                          />
                        )}
                        <div className="annex-task-text">
                          <span className="annex-task-name">
                            {task.title}
                            {task.is_overdue && <span className="annex-overdue">Vencida</span>}
                          </span>
                          <span className="annex-task-meta">
                            {assigneeName(task.assigned_user_id)}
                            {task.due_date ? `, vence el ${new Date(task.due_date).toLocaleDateString("es-CO", { day: "numeric", month: "short" })}` : ""}
                          </span>
                          <span className="annex-task-links">
                            {task.status === "pending" && (
                              <button type="button" className="acta-link" onClick={() => moveMutation.mutate({ taskId: task.id, status: "in_progress" })}>
                                Empezar
                              </button>
                            )}
                            {hecha && (
                              <button type="button" className="acta-link" onClick={() => moveMutation.mutate({ taskId: task.id, status: "pending" })}>
                                Reabrir
                              </button>
                            )}
                            <button type="button" className="acta-link"
                              onClick={() => setExpandedTaskId(expandedTaskId === task.id ? null : task.id)}>
                              {expandedTaskId === task.id ? "Ocultar comentarios" : "Comentarios"}
                            </button>
                          </span>
                        </div>
                      </div>
                      {expandedTaskId === task.id && <TaskComments taskId={task.id} />}
                    </li>
                  );
                })}
              </ul>
              {enColumna.length === 0 && <p className="acta-empty">Sin tareas.</p>}
            </div>
          );
        })}
      </div>
    </section>
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
  const { hasPermission, user } = useAuth();
  // Contabilidad abre el acta para cobrar pero no ve evidencias: sin esto la
  // pantalla las pedía igual y recibía 403 (QA-REG-10).
  const puedeVerEvidencias = hasPermission("evidence.read_all") || hasPermission("evidence.read_assigned");
  // El presupuesto de la obra: lo ve quien lo arma, quien lo aprueba y quien solo
  // tiene lectura de bodega (Gerencia). Los mismos permisos que exige la API.
  const puedeVerPresupuesto = hasAnyPermission(["budgets.manage", "budgets.approve", "warehouse.read"], user);
  // El diario de obra: lo escribe el técnico y lo lee quien mira la bodega.
  const puedeVerDiario = hasAnyPermission(["daylogs.manage", "warehouse.read"], user);
  // De dónde se llegó (la Agenda o la lista de proyectos lo pasan al abrir).
  // Sin eso, por ejemplo con un enlace directo, se vuelve a Proyectos.
  const volver = (useLocation().state as { backTo?: string; backLabel?: string } | null) ?? {};
  const backTo = volver.backTo ?? "/projects";
  const backLabel = volver.backLabel ?? "Proyectos";
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
    enabled: !!projectId && puedeVerEvidencias,
  });
  const evidence = evidenceData?.items;
  const [selectedEvidence, setSelectedEvidence] = useState<Evidence | null>(null);

  useEffect(() => {
    geo.request();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  const { data: catalogs } = useFieldCatalogs();
  const [category, setCategory] = useState<EvidenceCategory>("additional_photo");
  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);

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

  const recordData = useRecordData(projectId!, project?.status === "completed");
  const paso = useSearchParams()[0].get("paso");
  const proyectoListo = Boolean(project);
  useEffect(() => {
    if (paso && proyectoListo) openActaStep(paso);
  }, [paso, proyectoListo]);
  const { data: installers } = useInstallers(hasPermission("dispatch.manage"));

  if (projectLoading || !project) return <p>Cargando...</p>;
  const cerrada = project.status === "completed";
  const estados = deriveStates(project, recordData);
  const technicianName = project.primary_technician_user_id
    ? project.primary_technician_user_id === user?.id
      ? user.full_name
      : installers?.find((t) => t.id === project.primary_technician_user_id)?.full_name ?? "Asignado"
    : null;

  return (
    <div className="acta-page">
      <Link to={backTo} className="acta-back">
        <span aria-hidden="true">‹</span> Volver a {backLabel}
      </Link>
      <InstallationRecord
        project={project}
        technicianName={technicianName}
        steps={[
          {
            key: "permit", title: "Permiso municipal", ...estados.permit,
            body: <PermitsPanel projectId={project.id} canManage={hasPermission("permits.manage")} />,
          },
          {
            key: "release", title: "Orden liberada", ...estados.release,
            body: (
              <>
                <ReleaseOrderStep project={project} canSchedule={hasPermission("dispatch.manage")} />
                <h4 className="acta-section-title">Materiales de la orden</h4>
                <MaterialsPanel projectId={project.id} canManage={hasPermission("projects.update")} closed={cerrada} />
              </>
            ),
          },
          {
            key: "checklist", title: "Checklist técnico", ...estados.checklist,
            body: (
              <>
                <ConditionsPanel project={project} canEdit={hasPermission("checklists.complete")} />
                <ChecklistPanel project={project} items={checklist ?? []}
                  canEdit={hasPermission("checklists.complete")} coords={geo.coords} />
              </>
            ),
          },
          {
            key: "equipment", title: "Equipos instalados", ...estados.equipment,
            body: <EquipmentPanel projectId={project.id} canManage={hasPermission("equipment.manage")} closed={cerrada}
              confirmedAt={project.equipment_confirmed_at} />,
          },
          {
            key: "signatures", title: "Firmas del acta", ...estados.signatures,
            body: <SignaturesPanel projectId={project.id} canSign={hasPermission("evidence.create")} />,
          },
          {
            key: "close", title: "Cierre de la instalación", ...estados.close,
            body: (
              <CloseInstallationStep project={project} canClose={hasPermission("checklists.complete")}
                requirements={closeRequirements(project, recordData)} />
            ),
          },
          {
            key: "review", title: "Confirmación de Administración", ...estados.review,
            body: <ReviewStep project={project} canReview={hasPermission("checklists.approve")} />,
          },
          {
            key: "inspection", title: "Inspección municipal", ...estados.inspection,
            body: (
              <InspectionsPanel projectId={project.id} canManage={hasPermission("inspections.manage")}
                installationClosed={cerrada} />
            ),
          },
          {
            key: "billing", title: "Cobro al programa", ...estados.billing,
            body: (
              <BillingStep project={project} canCreate={hasPermission("billing.submit")}
                canRead={hasPermission("invoices.read")} />
            ),
          },
        ]}
      />

      <section className="acta acta-annex" aria-label="Anexos del acta">
        <header className="annex-header">
          <div>
            <h2 className="acta-title">Anexos</h2>
            <p className="acta-lead">Evidencias y tareas internas de esta instalación. Las firmas están en el paso «Firmas del acta».</p>
          </div>
          <span className={`annex-gps ${geo.status === "granted" && geo.coords ? "is-on" : "is-off"}`}>
            <PinIcon size={16} />
            {geo.status === "granted" && geo.coords
              ? <>GPS activo: <strong>{geo.coords.latitude.toFixed(4)}, {geo.coords.longitude.toFixed(4)}</strong></>
              : geo.status === "denied" ? "Sin GPS: las fotos quedarán marcadas «sin GPS»" : "Buscando GPS…"}
          </span>
        </header>

        {puedeVerEvidencias && (
        <section className="annex-section" aria-labelledby="anexo-evidencias">
          <div className="annex-section-head">
            <h3 id="anexo-evidencias">Evidencias</h3>
            <span className="annex-count">{evidenceData?.total ?? 0} archivos</span>
          </div>
          <p className="acta-lead">
            Las fotos del checklist se toman desde su línea; aquí van las adicionales.
          </p>
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
              <input type="file" hidden accept="image/*,video/mp4,video/quicktime,video/webm" capture="environment"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
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
          <p className="annex-note"><PinIcon size={14} /> Ubicación GPS y hora grabadas automáticamente en cada archivo.</p>
            <div className="annex-thumbs">
              {(evidence ?? []).length > 0
                ? (evidence ?? []).map((ev) => <EvidenceCard key={ev.id} evidence={ev} onOpen={setSelectedEvidence} />)
                : <p className="acta-empty">Todavía no hay evidencias.</p>}
            </div>

          {selectedEvidence && <EvidenceViewer evidence={selectedEvidence} onClose={() => setSelectedEvidence(null)} />}
          {evidenceData && evidenceData.total > EVIDENCE_PAGE_SIZE && (
            <PaginationControls page={evidencePage} pageSize={EVIDENCE_PAGE_SIZE} total={evidenceData.total} onPageChange={setEvidencePage} />
          )}
        </section>
        )}

        <TaskBoard projectId={project.id} />

        {puedeVerPresupuesto && <ProjectBudgetPanel projectId={project.id} />}

        {puedeVerDiario && <ProjectDayLogPanel projectId={project.id} />}
      </section>
    </div>
  );
}
