import { useEffect, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";

import { getProjectChecklist } from "@/features/field-ops/api";
import {
  fieldKeys,
  getInstallationGaps,
  listEquipment,
  listInspections,
  listPermits,
} from "@/features/field-ops/module5Api";
import type { Project } from "@/types/fieldOps";
import { CheckCircleIcon, CheckIcon, ClockIcon, DotIcon, LockIcon } from "./icons";

const STATE_CHIP: Record<StepState, { label: string; icon: ReactNode }> = {
  done: { label: "Completado", icon: <CheckCircleIcon size={16} /> },
  current: { label: "En curso", icon: <DotIcon size={14} /> },
  pending: { label: "Pendiente", icon: <ClockIcon size={16} /> },
  locked: { label: "Bloqueado", icon: <LockIcon size={15} /> },
};

export type StepState = "done" | "current" | "pending" | "locked";

export interface RecordStep {
  key: string;
  title: string;
  state: StepState;
  /** Una línea: qué quedó hecho, o qué falta para habilitarlo. */
  summary?: string;
  /** Texto del chip en vez del genérico del estado ("Pagado", "Rechazado"). */
  chip?: string;
  body: ReactNode;
}

const STAGE_ORDER = [
  "approved", "permit_in_progress", "ready_to_install", "installed",
  "inspection_pending", "billing_in_progress", "paid", "closed",
];

function stageAtLeast(project: Project, stage: string): boolean {
  const actual = project.case_stage_code;
  if (!actual) return false;
  return STAGE_ORDER.indexOf(actual) >= STAGE_ORDER.indexOf(stage);
}

function shortDate(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso.length === 10 ? `${iso}T12:00:00` : iso);
  return d.toLocaleDateString("es-CO", { day: "numeric", month: "short" });
}

/**
 * Los datos que el acta necesita para saber en qué paso va. Son las mismas
 * consultas que usan los pasos por dentro (misma clave), así que no se piden
 * dos veces.
 */
export function useRecordData(projectId: string, closed: boolean) {
  const permits = useQuery({ queryKey: fieldKeys.permits(projectId), queryFn: () => listPermits(projectId) });
  const equipment = useQuery({ queryKey: fieldKeys.equipment(projectId), queryFn: () => listEquipment(projectId) });
  const inspections = useQuery({ queryKey: fieldKeys.inspections(projectId), queryFn: () => listInspections(projectId) });
  const checklist = useQuery({ queryKey: fieldKeys.checklist(projectId), queryFn: () => getProjectChecklist(projectId) });
  const gaps = useQuery({
    queryKey: fieldKeys.gaps(projectId),
    queryFn: () => getInstallationGaps(projectId),
    enabled: !closed,
  });
  return {
    permits: permits.data ?? [],
    equipment: equipment.data ?? [],
    inspections: inspections.data ?? [],
    checklist: checklist.data ?? [],
    gaps: gaps.data,
  };
}

/**
 * Calcula el estado de cada paso a partir de los hechos registrados y la etapa
 * del expediente. El orden del acta es el orden real del trabajo en campo.
 */
export function deriveStates(project: Project, data: ReturnType<typeof useRecordData>) {
  const closed = project.status === "completed";
  const permitsCleared = data.permits.length > 0 && data.permits.every((p) => p.is_cleared);
  const released = Boolean(project.scheduled_date && project.primary_technician_user_id);
  const required = data.checklist.filter((i) => i.is_required &&
    (!i.condition_code || (project.installation_conditions ?? []).includes(i.condition_code)));
  const confirmed = required.filter((i) => i.is_complete || i.not_applicable).length;
  const checklistDone = required.length > 0 && confirmed === required.length;
  const lastInspection = data.inspections[data.inspections.length - 1];
  const inspectionPassed = lastInspection?.result === "passed";

  const done = {
    permit: permitsCleared || stageAtLeast(project, "ready_to_install"),
    release: released,
    checklist: checklistDone || closed,
    equipment: (data.equipment.length > 0 && Boolean(project.equipment_confirmed_at)) || closed,
    close: closed,
    review: Boolean(project.technician_info_confirmed),
    inspection: inspectionPassed,
    billing: stageAtLeast(project, "paid"),
  };
  const order: (keyof typeof done)[] = [
    "permit", "release", "checklist", "equipment", "close", "review", "inspection", "billing",
  ];
  const current = order.find((k) => !done[k]);

  const state = (k: keyof typeof done, lockedWhen = false): StepState =>
    done[k] ? "done" : lockedWhen ? "locked" : k === current ? "current" : "pending";

  const lastPermit = data.permits[data.permits.length - 1];
  return {
    permit: {
      state: state("permit"),
      summary: permitsCleared
        ? `Aprobado${lastPermit?.approved_on ? ` el ${shortDate(lastPermit.approved_on)}` : ""}${lastPermit?.expires_on ? `, vence el ${shortDate(lastPermit.expires_on)}` : ""}`
        : data.permits.length ? "Radicado, esperando aprobación" : "Sin radicar",
    },
    release: {
      state: state("release"),
      summary: released ? `Agendada para el ${shortDate(project.scheduled_date)}` : "Sin técnico ni fecha",
    },
    checklist: {
      state: state("checklist"),
      summary: `${confirmed} de ${required.length} confirmados`,
    },
    equipment: {
      state: state("equipment"),
      summary: !data.equipment.length
        ? "Ninguno registrado"
        : project.equipment_confirmed_at || closed
          ? data.equipment.map((e) => `${e.brand} ${e.model}`).join(", ")
          : `${data.equipment.length === 1 ? "1 registrado" : `${data.equipment.length} registrados`}, falta guardar la lista`,
    },
    close: {
      state: state("close"),
      summary: closed
        ? `Cerrada el ${shortDate(project.completed_date)}`
        : project.returned_reason ? `Devuelta para corregir: ${project.returned_reason}`
        : data.gaps && !data.gaps.can_close ? `Faltan ${data.gaps.missing.length}` : "Lista para cerrar",
    },
    review: {
      state: state("review", !closed),
      summary: project.technician_info_confirmed
        ? "Información técnica confirmada por Administración"
        : closed ? "Esperando la revisión de Administración" : "Se habilita al cerrar la instalación",
    },
    inspection: {
      state: state("inspection", !closed && !lastInspection),
      summary: inspectionPassed
        ? `Aprobada${data.inspections.length > 1 ? ` en el intento ${data.inspections.length}` : ""}`
        : lastInspection?.result === "pending" ? `Agendada para el ${shortDate(lastInspection.scheduled_for)}`
        : lastInspection?.result === "failed" ? "Fallida: la orden volvió a campo"
        : "Se habilita al cerrar la instalación",
    },
    billing: {
      state: state("billing", !project.technician_info_confirmed),
      summary: stageAtLeast(project, "paid") ? "Pagado por el programa"
        : project.case_stage_code === "billing_in_progress"
          ? (BILLING_SUBSTATUS[project.case_substatus_code ?? ""] ?? "En proceso de cobro")
          : project.technician_info_confirmed ? "Listo para crear el cobro" : "Se habilita al confirmar el acta",
    },
  };
}

const BILLING_SUBSTATUS: Record<string, string> = {
  invoice_pending: "En cobro: falta radicar",
  submitted: "En cobro: radicado, esperando pago",
  rejected_by_program: "En cobro: rechazado, en corrección",
};

/**
 * La lista de pasos con riel numerado del acta. La usan el acta de instalación
 * y las hojas del módulo 6 (cobro y cotización): el mismo lenguaje visual para
 * todo lo que es un proceso en orden.
 */
export function ActaSteps({ steps }: { steps: RecordStep[] }) {
  // Abierto por defecto: el paso actual. Los demás se abren a mano.
  const [open, setOpen] = useState<Set<string>>(() => new Set(steps.filter((s) => s.state === "current").map((s) => s.key)));
  // Al completarse un paso, el siguiente se abre solo: el acta guía sin que
  // haya que buscar dónde sigue.
  const currentKey = steps.find((s) => s.state === "current")?.key;
  useEffect(() => {
    if (currentKey) setOpen((prev) => (prev.has(currentKey) ? prev : new Set(prev).add(currentKey)));
  }, [currentKey]);

  const toggle = (key: string) =>
    setOpen((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key); else next.add(key);
      return next;
    });

  return (
    <ol className="acta-steps">
      {steps.map((step, n) => {
        const isOpen = open.has(step.key) && step.state !== "locked";
        return (
          <li key={step.key} className={`acta-step is-${step.state}`}>
            <span className="acta-step-marker" aria-hidden="true">
              {step.state === "done" ? <CheckIcon size={16} strokeWidth={2.6} /> : n + 1}
            </span>
            <button
              type="button"
              className="acta-step-head"
              aria-expanded={isOpen}
              disabled={step.state === "locked"}
              onClick={() => toggle(step.key)}
            >
              <span className="acta-step-text">
                <span className="acta-step-title">{step.title}</span>
                {step.summary && <span className="acta-step-summary">{step.summary}</span>}
              </span>
              <span className={`acta-chip is-${step.state}`}>
                {STATE_CHIP[step.state].icon}
                {step.chip ?? STATE_CHIP[step.state].label}
              </span>
            </button>
            {isOpen && <div className="acta-step-body"><div className="acta-step-card">{step.body}</div></div>}
          </li>
        );
      })}
    </ol>
  );
}

export function InstallationRecord({ project, technicianName, steps }: {
  project: Project;
  technicianName: string | null;
  steps: RecordStep[];
}) {
  return (
    <article className="acta" aria-label="Acta de instalación">
      <header className="acta-header">
        <div className="acta-title-row">
          <h1 className="acta-title">Acta de instalación</h1>
          {project.case_stage_label && (
            <span className="acta-stage">
              {/* El sub-estado dice más que la etapa cuando existe. */}
              {project.case_substatus_code === "install_scheduled" ? "Orden liberada"
                : project.case_substatus_code === "inspection_approved" ? "Inspección aprobada"
                : project.case_substatus_code && BILLING_SUBSTATUS[project.case_substatus_code]
                  ? BILLING_SUBSTATUS[project.case_substatus_code]
                : project.case_stage_label}
            </span>
          )}
        </div>
        <dl className="acta-meta">
          <div><dt>Expediente</dt><dd className="acta-data">{project.case_number ?? "Sin expediente"}</dd></div>
          <div>
            <dt>Dirección</dt>
            <dd>{[project.address_street, project.address_unit, project.address_city].filter(Boolean).join(", ")}</dd>
          </div>
          <div><dt>Técnico</dt><dd>{technicianName ?? "Sin asignar"}</dd></div>
          <div><dt>Fecha</dt><dd>{project.scheduled_date ? shortDate(project.scheduled_date) : "Sin agendar"}</dd></div>
        </dl>
      </header>
      <ActaSteps steps={steps} />
    </article>
  );
}

export interface Requirement {
  label: string;
  done: boolean;
}

/**
 * Todo lo que exige el cierre, cumplido o no, en el orden del acta. Misma
 * regla que el backend (`installation_gaps`): las líneas obligatorias que
 * aplican a esta casa, más al menos un equipo registrado. El backend sigue
 * siendo quien decide si se puede cerrar; esto es para ver el avance.
 */
export function closeRequirements(project: Project, data: ReturnType<typeof useRecordData>): Requirement[] {
  const condiciones = project.installation_conditions ?? [];
  const lineas = data.checklist
    .filter((i) => i.is_required && (!i.condition_code || condiciones.includes(i.condition_code)))
    .map((i) => ({ label: i.label, done: i.is_complete || i.not_applicable }));
  const equipo = data.equipment[0];
  return [
    ...lineas,
    {
      label: equipo
        ? `Equipo instalado registrado (${equipo.brand} ${equipo.model})`
        : "Registrar al menos un equipo instalado (marca, modelo y serial)",
      done: data.equipment.length > 0,
    },
    ...(data.equipment.length > 0
      ? [{ label: "Guardar la lista de equipos instalados", done: Boolean(project.equipment_confirmed_at) }]
      : []),
  ];
}
