import { useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { uploadEvidence, updateChecklistItem } from "@/features/field-ops/api";
import { apiErrorMessage, useFieldCatalogs, useRefreshProject } from "@/features/field-ops/module5Api";
import type { Project, ProjectChecklistItem } from "@/types/fieldOps";

interface Props {
  project: Project;
  items: ProjectChecklistItem[];
  canEdit: boolean;
  coords: { latitude: number; longitude: number } | null;
}

function stampTime(iso: string | null | undefined): string {
  if (!iso) return "";
  return new Date(iso).toLocaleString("es-CO", { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });
}

/**
 * El checklist como líneas de acta (requerimientos §8): cada línea se
 * confirma y queda sellada con la hora, o se marca "No aplica" con su motivo.
 * La numeración corre por todo el acta, no por sección: es la referencia que
 * Administración usa al hablar con el técnico ("la línea 9").
 */
export function ChecklistPanel({ project, items, canEdit, coords }: Props) {
  const { data: catalogs } = useFieldCatalogs();
  const refresh = useRefreshProject(project.id);
  const [error, setError] = useState<string | null>(null);
  const cerrado = project.status === "completed";
  const condiciones = project.installation_conditions ?? [];

  const secciones: [string, ProjectChecklistItem[]][] = [];
  for (const item of items) {
    const nombre = item.section ?? "Checklist";
    const ultima = secciones[secciones.length - 1];
    if (ultima && ultima[0] === nombre) ultima[1].push(item);
    else secciones.push([nombre, [item]]);
  }
  let linea = 0;

  return (
    <div className="acta-body">
      {error && <p className="form-error" role="alert">{error}</p>}
      {items.length === 0 && <p className="acta-empty">Este proyecto no tiene checklist.</p>}
      {secciones.map(([seccion, lista]) => (
        <section key={seccion} className="acta-section">
          <h4 className="acta-section-title">{seccion}</h4>
          <ol className="acta-items">
            {lista.map((item) => {
              linea += 1;
              return (
                <ChecklistLine
                  key={item.id}
                  number={linea}
                  item={item}
                  applies={!item.condition_code || condiciones.includes(item.condition_code)}
                  conditionLabel={item.condition_code ? catalogs?.installation_conditions[item.condition_code] : undefined}
                  categoryLabel={item.evidence_category ? catalogs?.evidence_categories[item.evidence_category] : undefined}
                  disabled={!canEdit || cerrado}
                  projectId={project.id}
                  coords={coords}
                  onError={setError}
                  onChanged={() => {
                    setError(null);
                    return refresh();
                  }}
                />
              );
            })}
          </ol>
        </section>
      ))}
    </div>
  );
}

interface LineProps {
  number: number;
  item: ProjectChecklistItem;
  applies: boolean;
  conditionLabel?: string;
  categoryLabel?: string;
  disabled: boolean;
  projectId: string;
  coords: { latitude: number; longitude: number } | null;
  onError: (message: string) => void;
  onChanged: () => Promise<unknown>;
}

function ChecklistLine({ number, item, applies, conditionLabel, categoryLabel, disabled, projectId, coords, onError, onChanged }: LineProps) {
  const [askingReason, setAskingReason] = useState(false);
  const [reason, setReason] = useState("");

  const update = useMutation({
    mutationFn: (change: { is_complete?: boolean; not_applicable?: boolean; reason?: string }) =>
      updateChecklistItem(item.id, change),
    onSuccess: () => {
      setAskingReason(false);
      setReason("");
      return onChanged();
    },
    onError: (err) => onError(apiErrorMessage(err, "No se pudo actualizar la línea.")),
  });

  const upload = useMutation({
    mutationFn: (file: File) =>
      uploadEvidence(projectId, file, { checklistItemId: item.id, latitude: coords?.latitude, longitude: coords?.longitude }),
    // Con la foto arriba, la línea se confirma sola: un toque para el técnico.
    onSuccess: () => update.mutate({ is_complete: true }),
    onError: (err) => onError(apiErrorMessage(err, "No se pudo subir la foto.")),
  });

  const resolved = item.is_complete || item.not_applicable;
  const estado = !applies ? "is-inactive" : item.is_complete ? "is-confirmed" : item.not_applicable ? "is-na" : "is-open";
  const actionable = !disabled && applies;

  return (
    <li className={`acta-item ${estado}`}>
      <span className="acta-item-num">{number}</span>
      <div className="acta-item-main">
        <p className="acta-item-label">{item.label}</p>
        {!applies && conditionLabel && <p className="acta-item-note">No se exige: solo aplica si «{conditionLabel.toLowerCase()}».</p>}
        {applies && !resolved && item.requires_evidence && categoryLabel && (
          <p className="acta-item-note">Requiere foto: {categoryLabel.toLowerCase()}.</p>
        )}
        {item.is_complete && <p className="acta-stamp">Confirmado el {stampTime(item.completed_at)}</p>}
        {item.not_applicable && <p className="acta-stamp is-na">No aplica: {item.not_applicable_reason}</p>}

        {askingReason && (
          <form className="acta-reason" onSubmit={(e) => { e.preventDefault(); update.mutate({ not_applicable: true, reason }); }}>
            <label htmlFor={`motivo-${item.id}`}>Por qué no aplica</label>
            <input id={`motivo-${item.id}`} value={reason} onChange={(e) => setReason(e.target.value)}
              placeholder="La casa no tiene panel propio" autoFocus />
            <div className="acta-actions">
              <button type="submit" className="acta-btn" disabled={update.isPending}>Guardar motivo</button>
              <button type="button" className="acta-btn is-quiet" onClick={() => setAskingReason(false)}>Cancelar</button>
            </div>
          </form>
        )}
      </div>

      {actionable && !askingReason && (
        <div className="acta-actions">
          {!resolved && item.requires_evidence && (
            <label className="acta-btn is-primary">
              {upload.isPending ? "Subiendo…" : "Tomar foto"}
              <input type="file" accept="image/*,video/mp4,video/quicktime,video/webm" capture="environment" hidden
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) upload.mutate(file);
                  e.target.value = "";
                }} />
            </label>
          )}
          {!resolved && item.allows_not_applicable && (
            <button type="button" className="acta-btn is-quiet" onClick={() => setAskingReason(true)}>No aplica</button>
          )}
          {!resolved && (
            <button type="button" className={`acta-btn ${item.requires_evidence ? "is-quiet" : "is-primary"}`}
              disabled={update.isPending} onClick={() => update.mutate({ is_complete: true })}>
              Confirmar
            </button>
          )}
          {resolved && (
            <button type="button" className="acta-btn is-quiet" disabled={update.isPending}
              onClick={() => update.mutate({ is_complete: false })}>
              Deshacer
            </button>
          )}
        </div>
      )}
    </li>
  );
}
