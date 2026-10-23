/** Iniciales de un nombre: «Ana Torres» → «AT», «Retail» → «RE». */
export function iniciales(nombre: string | null | undefined): string {
  const partes = (nombre ?? "").trim().split(/\s+/).filter(Boolean);
  if (partes.length === 0) return "?";
  if (partes.length === 1) return partes[0].slice(0, 2).toUpperCase();
  return (partes[0][0] + partes[partes.length - 1][0]).toUpperCase();
}

// Seis tonos suaves; el mismo nombre siempre cae en el mismo.
const TONOS = 6;
function tono(nombre: string): number {
  let h = 0;
  for (const c of nombre) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  return h % TONOS;
}

/** Círculo con iniciales (propuesta UI/UX V1). Decorativo: el nombre va al lado. */
export function Avatar({ name, size = "md" }: { name: string | null | undefined; size?: "sm" | "md" | "lg" }) {
  return (
    <span className={`ui-avatar is-${size} is-t${tono(name ?? "")}`} aria-hidden="true">
      {iniciales(name)}
    </span>
  );
}
