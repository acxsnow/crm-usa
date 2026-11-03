// Render sirve /404.html cuando una ruta no es un archivo. Sin esto, abrir una URL
// directa da 404: también los enlaces que recibe el cliente (/pagar, /cotizacion).
import { copyFileSync } from "node:fs";

copyFileSync("dist/index.html", "dist/404.html");
