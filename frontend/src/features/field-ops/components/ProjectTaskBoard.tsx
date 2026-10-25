import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { createTask, createTaskComment, getProjectAssignments, listProjectTasks, listTaskComments, updateTask } from "../api";
import { useInstallers } from "../module5Api";
import { CheckCircleIcon, CheckIcon, ClockIcon, GearIcon } from "./icons";
import { type FieldTask, type TaskStatus } from "@/types/fieldOps";
import { useAuth } from "@/features/auth/AuthContext";

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

export function ProjectTaskBoard({ projectId }: { projectId: string }) {
  const queryClient = useQueryClient();
  const { data: tasks } = useQuery({ queryKey: ["project-tasks", projectId], queryFn: () => listProjectTasks(projectId) });
  const { hasPermission } = useAuth();
  const { data: installers } = useInstallers(hasPermission("dispatch.manage"));
  const { data: turnos } = useQuery({
    queryKey: ["project-assignments", projectId],
    queryFn: () => getProjectAssignments(projectId),
  });

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
    const installer = installers?.find((u) => u.id === userId);
    if (installer) return installer.full_name;
    const turno = turnos?.find((t) => t.technician_user_id === userId);
    return turno?.technician_name ?? "Asignado";
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
          <input
            id="tarea-titulo"
            placeholder="Llevar soporte antivibración"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            required
          />
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
                            {task.due_date
                              ? `, vence el ${new Date(task.due_date).toLocaleDateString("es-CO", { day: "numeric", month: "short" })}`
                              : ""}
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
                            <button
                              type="button"
                              className="acta-link"
                              onClick={() => setExpandedTaskId(expandedTaskId === task.id ? null : task.id)}
                            >
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
