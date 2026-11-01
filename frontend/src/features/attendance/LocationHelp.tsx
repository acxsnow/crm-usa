/** Cómo activar la ubicación: si se negó, el navegador no vuelve a preguntar solo. */
export function LocationHelp() {
  return (
    <div className="att-gate-help" role="alert">
      <strong>Tu navegador tiene bloqueada la ubicación</strong>
      <p>Actívala y vuelve a intentarlo. Si no puedes, registra una novedad.</p>
      <ul>
        <li><b>iPhone:</b> Ajustes › Privacidad y seguridad › Localización › Safari › «Al usar la app»; luego, en Safari, «aA» › Ajustes del sitio web › Ubicación › Permitir.</li>
        <li><b>Android (Chrome):</b> toca el ícono junto a la dirección › Permisos › Ubicación › Permitir.</li>
        <li><b>App instalada en el celular:</b> en los ajustes del teléfono, busca el navegador o la app y permite la ubicación.</li>
      </ul>
    </div>
  );
}
