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

/**
 * Checklist técnico agrupado por sección (requerimientos §8).
 *
 * - Un ítem condicional cuya condición no aplica a esta casa se muestra atenuado
 *   y no bloquea el cierre.
 * - "No aplica" pide el motivo en línea, sin diálogos.
 * - La foto de un ítem se sube desde el propio ítem: el backend le pone la
 *   categoría que el ítem exige.
 */
export function ChecklistPanel({ project, items, canEdit, coords }: Props) {
  const { data: catalogs } = useFieldCatalogs();
  const refresh = useRefreshProject(project.id);
  const [error, setError] = useState<string | null>(null);
  const cerrado = project.status === "completed";
  const condiciones = project.installation_conditions ?? [];

  const secciones = new Map<string, ProjectChecklistItem[]>();
  for (const item of items) {
    const clave = item.section ?? "Checklist";
    secciones.set(clave, [...(secciones.get(clave) ?? []), item]);
  }

  return (
    <section className="panel">
      <div className="panel-heading">
        <h3>Checklist técnico</h3>
        {cerrado && <span className="status-pill status-completed">Congelado: instalación cerrada</span>}
      </div>
      {error && <p className="form-error" role="alert">{error}</p>}
      {items.length === 0 && <p className="empty-state">Este proyecto no tiene checklist.</p>}
      {[...secciones.entries()].map(([seccion, lista]) => (
        <div key={seccion}>
          <h4 className="eyebrow">{seccion}</h4>
          <ul className="plain-list">
            {lista.map((item) => (
              <ChecklistRow
                key={item.id}
                item={item}
                aplica={!item.condition_code || condiciones.includes(item.condition_code)}
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
            ))}
          </ul>
        </div>
      ))}
    </section>
  );
}

interface RowProps {
  item: ProjectChecklistItem;
  aplica: boolean;
  conditionLabel?: string;
  categoryLabel?: string;
  disabled: boolean;
  projectId: string;
  coords: { latitude: number; longitude: number } | null;
  onError: (message: string) => void;
  onChanged: () => Promise<unknown>;
}

function ChecklistRow({ item, aplica, conditionLabel, categoryLabel, disabled, projectId, coords, onError, onChanged }: RowProps) {
  const [pidiendoMotivo, setPidiendoMotivo] = useState(false);
  const [motivo, setMotivo] = useState("");

  const update = useMutation({
    mutationFn: (change: { is_complete?: boolean; not_applicable?: boolean; reason?: string }) =>
      updateChecklistItem(item.id, change),
    onSuccess: () => {
      setPidiendoMotivo(false);
      setMotivo("");
      return onChanged();
    },
    onError: (err) => onError(apiErrorMessage(err, "No se pudo actualizar el ítem.")),
  });

  const upload = useMutation({
    mutationFn: (file: File) =>
      uploadEvidence(projectId, file, {
        checklistItemId: item.id,
        latitude: coords?.latitude,
        longitude: coords?.longitude,
      }),
    onSuccess: onChanged,
    onError: (err) => onError(apiErrorMessage(err, "No se pudo subir la evidencia.")),
  });

  const inputId = `checklist-${item.id}`;
  return (
    <li style={{ opacity: aplica ? 1 : 0.55 }}>
      <div style={{ display: "flex", gap: "0.5rem", alignItems: "center", flexWrap: "wrap" }}>
        <input
          id={inputId}
          type="checkbox"
          checked={item.is_complete}
          disabled={disabled || update.isPending}
          onChange={(e) => update.mutate({ is_complete: e.target.checked })}
        />
        <label htmlFor={inputId}>{item.label}</label>
        {item.not_applicable && (
          <span className="status-pill status-inactive" title={item.not_applicable_reason ?? ""}>
            No aplica: {item.not_applicable_reason}
          </span>
        )}
        {categoryLabel && item.requires_evidence && !item.is_complete && !item.not_applicable && (
          <span className="status-pill status-pending">Foto: {categoryLabel}</span>
        )}
        {conditionLabel && <small>{aplica ? `Aplica: ${conditionLabel}` : `Solo si: ${conditionLabel}`}</small>}
        {!disabled && item.requires_evidence && !item.is_complete && !item.not_applicable && (
          <label className="link-button">
            {upload.isPending ? "Subiendo…" : "Subir foto"}
            <input
              type="file"
              accept="image/*,video/mp4,video/quicktime,video/webm"
              capture="environment"
              hidden
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) upload.mutate(file);
                e.target.value = "";
              }}
            />
          </label>
        )}
        {!disabled && item.allows_not_applicable && !item.not_applicable && !item.is_complete && !pidiendoMotivo && (
          <button type="button" className="link-button" onClick={() => setPidiendoMotivo(true)}>
            No aplica
          </button>
        )}
        {!disabled && item.not_applicable && (
          <button type="button" className="link-button" onClick={() => update.mutate({ is_complete: false })}>
            Deshacer
          </button>
        )}
      </div>
      {pidiendoMotivo && (
        <form
          className="inline-form"
          onSubmit={(e) => {
            e.preventDefault();
            update.mutate({ not_applicable: true, reason: motivo });
          }}
        >
          <input
            id={`${inputId}-motivo`}
            aria-label={`Motivo de «No aplica» para ${item.label}`}
            placeholder="Motivo (p. ej. la casa no tiene panel propio)"
            value={motivo}
            onChange={(e) => setMotivo(e.target.value)}
            autoFocus
          />
          <button type="submit" disabled={update.isPending}>Guardar</button>
          <button type="button" className="ghost-button" onClick={() => setPidiendoMotivo(false)}>Cancelar</button>
        </form>
      )}
    </li>
  );
}
