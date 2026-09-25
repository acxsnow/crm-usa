import { useMemo, useState } from "react";
import type { PermissionCatalog } from "@/types/users";

/**
 * Selector de permisos agrupado por módulo.
 *
 * El administrador piensa en módulos ("que Contabilidad vea Facturación"), no
 * en 72 códigos sueltos, así que se marcan por grupo y se pueden abrir para
 * ajustar el detalle.
 *
 * Un permiso puede pertenecer a varios módulos: aparece en cada uno, y marcarlo
 * desde cualquiera lo activa en todos, porque lo que se guarda es el permiso,
 * no su ubicación en el menú.
 */
export function PermissionPicker({
  catalog,
  selected,
  onChange,
  disabled = false,
}: {
  catalog: PermissionCatalog;
  selected: string[];
  onChange: (codes: string[]) => void;
  disabled?: boolean;
}) {
  const [openModules, setOpenModules] = useState<string[]>([]);
  const selectedSet = useMemo(() => new Set(selected), [selected]);
  const descriptions = useMemo(
    () => new Map(catalog.permissions.map((p) => [p.code, p.description])),
    [catalog.permissions]
  );

  function toggleModule(key: string) {
    setOpenModules((open) =>
      open.includes(key) ? open.filter((k) => k !== key) : [...open, key]
    );
  }

  function togglePermission(code: string) {
    if (disabled) return;
    onChange(
      selectedSet.has(code) ? selected.filter((c) => c !== code) : [...selected, code]
    );
  }

  function toggleWholeModule(permissions: string[], allSelected: boolean) {
    if (disabled) return;
    if (allSelected) {
      // Desmarcar el módulo quita todos sus permisos, sin excepciones. Si
      // alguno pertenece también a otro módulo, el contador de ese otro baja a
      // la vista: es una regla predecible. Una versión anterior intentaba
      // conservar los compartidos, y el resultado era que desmarcar un módulo
      // dejaba permisos marcados sin que se entendiera por qué.
      const delModulo = new Set(permissions);
      onChange(selected.filter((code) => !delModulo.has(code)));
    } else {
      onChange([...new Set([...selected, ...permissions])]);
    }
  }

  return (
    <div className="permission-picker">
      {catalog.modules.map((module) => {
        const marcados = module.permissions.filter((p) => selectedSet.has(p));
        const todos = marcados.length === module.permissions.length;
        const algunos = marcados.length > 0 && !todos;
        const abierto = openModules.includes(module.key);

        return (
          <div className="permission-module" key={module.key}>
            <div className="permission-module-header">
              <label className="permission-module-title">
                <input
                  type="checkbox"
                  checked={todos}
                  ref={(el) => {
                    if (el) el.indeterminate = algunos;
                  }}
                  disabled={disabled}
                  onChange={() => toggleWholeModule(module.permissions, todos)}
                />
                <span>{module.label}</span>
                <span className="permission-count">
                  {marcados.length}/{module.permissions.length}
                </span>
              </label>
              <button
                type="button"
                className="ghost-button permission-toggle"
                onClick={() => toggleModule(module.key)}
                aria-expanded={abierto}
              >
                {abierto ? "Ocultar detalle" : "Ver detalle"}
              </button>
            </div>

            {abierto && (
              <ul className="permission-list">
                {module.permissions.map((code) => (
                  <li key={`${module.key}-${code}`}>
                    <label>
                      <input
                        type="checkbox"
                        checked={selectedSet.has(code)}
                        disabled={disabled}
                        onChange={() => togglePermission(code)}
                      />
                      <span>{descriptions.get(code) ?? code}</span>
                      <code>{code}</code>
                    </label>
                  </li>
                ))}
              </ul>
            )}
          </div>
        );
      })}
    </div>
  );
}
