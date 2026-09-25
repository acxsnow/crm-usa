import { Link } from "react-router-dom";

/**
 * Pantalla para cuando alguien llega a un módulo que no le corresponde.
 *
 * Importa que diga qué pasó y ofrezca salida: antes, entrar por URL a una
 * sección ajena mostraba una tabla vacía o una pantalla en blanco, que parece
 * un error del sistema y no una restricción de acceso.
 */
export function NoAccess({ moduleLabel }: { moduleLabel?: string }) {
  return (
    <div className="no-access">
      <span className="no-access-icon" aria-hidden="true">⚿</span>
      <h1>No tienes acceso a esta sección</h1>
      <p>
        {moduleLabel
          ? `Tu rol no incluye acceso a ${moduleLabel}.`
          : "Tu rol no incluye acceso a esta sección."}{" "}
        Si crees que deberías tenerlo, pídeselo al administrador.
      </p>
      <Link className="primary-button" to="/">
        Volver al inicio
      </Link>
    </div>
  );
}
