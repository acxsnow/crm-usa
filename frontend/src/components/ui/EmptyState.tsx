import type { ReactNode } from "react";

/**
 * Lista vacía: qué pasa y, si quien mira puede hacer algo, la acción. La acción
 * la decide la pantalla según sus permisos; aquí solo se muestra.
 */
export function EmptyState({ title, description, action, icon = "○" }: {
  title: string;
  description?: ReactNode;
  action?: ReactNode;
  icon?: ReactNode;
}) {
  return (
    <div className="ui-empty">
      <span className="ui-empty-icon" aria-hidden="true">{icon}</span>
      <strong>{title}</strong>
      {description && <p>{description}</p>}
      {action}
    </div>
  );
}
