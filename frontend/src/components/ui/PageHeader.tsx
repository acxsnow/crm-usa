import type { ReactNode } from "react";

/**
 * Encabezado de página (propuesta UI/UX V1): título, descripción breve y las
 * acciones principales a la derecha; en el celular se apilan a todo el ancho.
 */
export function PageHeader({ title, description, eyebrow, actions }: {
  title: ReactNode;
  description?: ReactNode;
  eyebrow?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <header className="ui-page-header">
      <div>
        {eyebrow && <p className="eyebrow">{eyebrow}</p>}
        <h1>{title}</h1>
        {description && <p>{description}</p>}
      </div>
      {actions && <div className="ui-page-header-actions">{actions}</div>}
    </header>
  );
}
