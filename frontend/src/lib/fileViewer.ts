/**
 * Visor de archivos dentro de la página (foto, video o PDF). Antes «Ver» abría
 * una pestaña nueva después de descargar el archivo: el celular la bloqueaba
 * por no salir directo del toque y, abierta desde el ícono (modo app), la
 * pestaña con el archivo local quedaba en blanco. Ahora se muestra encima de la
 * pantalla, con «Cerrar» y «Descargar».
 */
export function showFile(blob: Blob, name = "archivo") {
  const url = URL.createObjectURL(blob);
  const tipo = blob.type || "";
  const capa = document.createElement("div");
  capa.className = "file-viewer";
  capa.setAttribute("role", "dialog");
  capa.setAttribute("aria-modal", "true");
  capa.setAttribute("aria-label", "Ver archivo");

  const barra = document.createElement("div");
  barra.className = "file-viewer-bar";
  const bajar = document.createElement("a");
  bajar.href = url;
  bajar.download = name;
  bajar.textContent = "Descargar";
  bajar.className = "file-viewer-btn";
  const cerrar = document.createElement("button");
  cerrar.type = "button";
  cerrar.textContent = "Cerrar";
  cerrar.className = "file-viewer-btn is-primary";
  barra.append(bajar, cerrar);

  let cuerpo: HTMLElement;
  if (tipo.startsWith("image/")) {
    const img = document.createElement("img");
    img.src = url;
    img.alt = name;
    cuerpo = img;
  } else if (tipo.startsWith("video/")) {
    const v = document.createElement("video");
    v.src = url;
    v.controls = true;
    v.playsInline = true;
    cuerpo = v;
  } else if (tipo === "application/pdf") {
    const f = document.createElement("iframe");
    f.src = url;
    f.title = name;
    cuerpo = f;
  } else {
    const p = document.createElement("p");
    p.textContent = "Este archivo no se puede mostrar aquí. Usa «Descargar».";
    cuerpo = p;
  }
  cuerpo.classList.add("file-viewer-body");
  capa.append(barra, cuerpo);

  const salir = () => {
    capa.remove();
    document.removeEventListener("keydown", tecla);
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  const tecla = (e: KeyboardEvent) => { if (e.key === "Escape") salir(); };
  cerrar.addEventListener("click", salir);
  capa.addEventListener("click", (e) => { if (e.target === capa) salir(); });
  document.addEventListener("keydown", tecla);
  document.body.append(capa);
  cerrar.focus();
}
