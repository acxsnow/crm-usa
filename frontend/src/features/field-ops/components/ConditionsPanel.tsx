import { useState } from "react";
import { useMutation } from "@tanstack/react-query";

import {
  apiErrorMessage,
  setInstallationConditions,
  useFieldCatalogs,
  useRefreshProject,
} from "@/features/field-ops/module5Api";
import type { Project } from "@/types/fieldOps";

/**
 * Condiciones de esta casa (requerimientos §8.3). Cada una vuelve obligatorios
 * ciertos ítems del checklist: retirar un furnace a gas exige la foto de la
 * desconexión.
 */
export function ConditionsPanel({ project, canEdit }: { project: Project; canEdit: boolean }) {
  const { data: catalogs } = useFieldCatalogs();
  const refresh = useRefreshProject(project.id);
  const [error, setError] = useState<string | null>(null);
  const actuales = project.installation_conditions ?? [];
  const bloqueado = !canEdit || project.status === "completed";

  const save = useMutation({
    mutationFn: (conditions: string[]) => setInstallationConditions(project.id, conditions),
    onSuccess: () => {
      setError(null);
      return refresh();
    },
    onError: (err) => setError(apiErrorMessage(err)),
  });

  if (!catalogs) return null;
  return (
    <section className="panel">
      <div className="panel-heading">
        <h3>Condiciones de la instalación</h3>
      </div>
      {error && <p className="form-error" role="alert">{error}</p>}
      <div style={{ display: "flex", gap: "1rem", flexWrap: "wrap" }}>
        {Object.entries(catalogs.installation_conditions).map(([code, label]) => {
          const id = `condicion-${code}`;
          return (
            <label key={code} htmlFor={id} style={{ display: "flex", gap: "0.4rem", alignItems: "center" }}>
              <input
                id={id}
                type="checkbox"
                checked={actuales.includes(code)}
                disabled={bloqueado || save.isPending}
                onChange={(e) =>
                  save.mutate(e.target.checked ? [...actuales, code] : actuales.filter((c) => c !== code))
                }
              />
              {label}
            </label>
          );
        })}
      </div>
    </section>
  );
}
