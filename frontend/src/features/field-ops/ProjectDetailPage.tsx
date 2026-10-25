import { useEffect, useState } from "react";
import { Link, useLocation, useParams, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  getProject,
  getProjectAssignments,
  getProjectChecklist,
} from "./api";
import { ProjectEvidencePanel } from "./components/ProjectEvidencePanel";
import { ProjectTaskBoard } from "./components/ProjectTaskBoard";
import { SignaturesPanel } from "./components/SignaturesPanel";
import { useAuth } from "@/features/auth/AuthContext";
import { useInstallers } from "./module5Api";
import { PinIcon } from "./components/icons";
import { ChecklistPanel } from "./components/ChecklistPanel";
import { ConditionsPanel } from "./components/ConditionsPanel";
import { EquipmentPanel } from "./components/EquipmentPanel";
import { InspectionsPanel } from "./components/InspectionsPanel";
import { CloseInstallationStep, ReleaseOrderStep } from "./components/InstallationPanel";
import { CancelProjectStep, FailedVisitsStep } from "./components/VisitsPanel";
import { InstallationRecord, closeRequirements, deriveStates, openActaStep, useRecordData } from "./components/InstallationRecord";
import { MaterialsPanel } from "./components/MaterialsPanel";
import { PermitsPanel } from "./components/PermitsPanel";
import { ReviewStep } from "./components/ReviewStep";
import { BillingStep } from "./components/BillingStep";
import { JobCostPanel } from "@/features/warehouse/JobCostPanel";
import { ExtraChargeForm } from "@/features/warehouse/ExtraChargeForm";
import { ProjectDayLogPanel } from "@/features/warehouse/ProjectDayLogPanel";
import { ProjectMiniMap } from "@/features/map/ProjectMiniMap";
import { ProjectCollect } from "@/features/payments/ProjectCollect";
import { hasAnyPermission } from "@/config/navigation";


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
  // El técnico anota el cobro adicional que recibió en la obra; la oficina lo ve en «Costo del trabajo».
  const puedeAnotarExtra = !puedeVerPresupuesto && hasAnyPermission(["daylogs.manage"], user);
  // De dónde se llegó (la Agenda o la lista de proyectos lo pasan al abrir).
  // Sin eso, por ejemplo con un enlace directo, se vuelve a Proyectos.
  const volver = (useLocation().state as { backTo?: string; backLabel?: string } | null) ?? {};
  const backTo = volver.backTo ?? "/projects";
  const backLabel = volver.backLabel ?? "Proyectos";
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
  useEffect(() => {
    geo.request();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  const recordData = useRecordData(projectId!, project?.status === "completed");
  const paso = useSearchParams()[0].get("paso");
  const proyectoListo = Boolean(project);
  useEffect(() => {
    if (paso && proyectoListo) openActaStep(paso);
  }, [paso, proyectoListo]);
  const { data: installers } = useInstallers(hasPermission("dispatch.manage"));
  const { data: turnos } = useQuery({
    queryKey: ["project-assignments", projectId],
    queryFn: () => getProjectAssignments(projectId!),
    enabled: !!projectId,
  });

  if (projectLoading || !project) return <p>Cargando...</p>;
  const cerrada = project.status === "completed";
  // El técnico que fue responsable antes o va de ayudante ve la obra sin
  // llenarla: el personal rota y el nuevo sigue donde el otro terminó.
  const trabaja = project.my_access !== "read_only";
  const estados = deriveStates(project, recordData);
  const technicianName = project.primary_technician_user_id
    ? project.primary_technician_user_id === user?.id
      ? user.full_name
      : installers?.find((t) => t.id === project.primary_technician_user_id)?.full_name
        ?? turnos?.find((t) => t.current)?.technician_name ?? "Asignado"
    : null;

  return (
    <div className="acta-page">
      <Link to={backTo} className="acta-back">
        <span aria-hidden="true">‹</span> Volver a {backLabel}
      </Link>
      {project.status === "cancelled" && (
        <div className="info-banner read-only-banner" role="status">
          <strong>Obra cancelada.</strong> {project.cancel_reason ?? ""} Queda en solo lectura.
        </div>
      )}
      {!trabaja && project.status !== "cancelled" && (
        <div className="info-banner read-only-banner" role="status">
          <strong>Solo lectura.</strong> El técnico responsable de esta obra hoy es{" "}
          {turnos?.find((t) => t.current)?.technician_name ?? "otro técnico"}. Ves lo que se ha hecho y lo que se
          va haciendo, pero no la llenas.
        </div>
      )}
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
                <FailedVisitsStep project={project} coords={geo.coords}
                  canReport={hasPermission("checklists.complete") && trabaja}
                  canSchedule={hasPermission("dispatch.manage")} />
                <CancelProjectStep project={project} canCancel={hasPermission("projects.close")} />
                <h4 className="acta-section-title">Materiales de la orden</h4>
                <MaterialsPanel projectId={project.id} canManage={hasPermission("projects.update") && trabaja} closed={cerrada} />
                <AssignmentsHistory projectId={project.id} />
              </>
            ),
          },
          {
            key: "checklist", title: "Checklist técnico", ...estados.checklist,
            body: (
              <>
                <ConditionsPanel project={project} canEdit={hasPermission("checklists.complete") && trabaja} />
                <ChecklistPanel project={project} items={checklist ?? []}
                  canEdit={hasPermission("checklists.complete") && trabaja} coords={geo.coords} />
              </>
            ),
          },
          {
            key: "equipment", title: "Equipos instalados", ...estados.equipment,
            body: <EquipmentPanel projectId={project.id} canManage={hasPermission("equipment.manage") && trabaja} closed={cerrada}
              confirmedAt={project.equipment_confirmed_at} />,
          },
          {
            key: "signatures", title: "Firmas del acta", ...estados.signatures,
            body: <SignaturesPanel projectId={project.id} canSign={hasPermission("evidence.create") && trabaja} />,
          },
          {
            key: "close", title: "Cierre de la instalación", ...estados.close,
            body: (
              <CloseInstallationStep project={project} canClose={hasPermission("checklists.complete") && trabaja}
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
          <ProjectEvidencePanel projectId={project.id} canUpload={trabaja} geoStatus={geo.status} coords={geo.coords} />
        )}

        <ProjectMiniMap projectId={project.id} />

        <ProjectCollect projectId={project.id} />

        <ProjectTaskBoard projectId={project.id} />

        {puedeVerPresupuesto && <JobCostPanel projectId={project.id} />}
        {puedeAnotarExtra && trabaja && (
          <section className="annex-section" aria-labelledby="anexo-extra">
            <div className="annex-section-head"><h3 id="anexo-extra">Cobro adicional del cliente</h3></div>
            <p className="acta-lead">
              Si el dueño de casa pidió algo extra (un breaker, más cable, mover algo) y lo pagó aparte, anótalo
              aquí y entrégale el efectivo a la oficina.
            </p>
            <ExtraChargeForm projectId={project.id} />
          </section>
        )}

        {puedeVerDiario && <ProjectDayLogPanel projectId={project.id} soloLectura={!trabaja} />}
      </section>
    </div>
  );
}

/**
 * Quién fue el técnico responsable de la obra (plan bodega-cierre, fase 5).
 * El personal rota: la «Orden liberada» se vuelve a guardar con otro técnico y
 * el nuevo sigue donde el otro terminó. Solo se muestra cuando ya hubo cambio.
 */
function AssignmentsHistory({ projectId }: { projectId: string }) {
  const { data: turnos } = useQuery({
    queryKey: ["project-assignments", projectId],
    queryFn: () => getProjectAssignments(projectId),
  });
  if (!turnos || turnos.length < 2) return null;
  const fecha = (iso: string) => new Date(`${iso}T12:00:00`).toLocaleDateString("es-CO", { day: "numeric", month: "short" });
  return (
    <div className="assignments-history">
      <h4 className="acta-section-title">Técnicos responsables de la obra</h4>
      <ol>
        {turnos.map((t, i) => (
          <li key={`${t.technician_user_id}-${i}`} className={t.current ? "is-current" : undefined}>
            <strong>{t.technician_name ?? "Técnico"}</strong>
            <span>
              {t.current ? `desde el ${fecha(t.started_on)} · responsable hoy`
                : `del ${fecha(t.started_on)} al ${fecha(t.ended_on ?? t.started_on)} · solo lectura`}
            </span>
          </li>
        ))}
      </ol>
    </div>
  );
}
