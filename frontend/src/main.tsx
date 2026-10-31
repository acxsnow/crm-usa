import React from "react";
import ReactDOM from "react-dom/client";
import { App } from "./App";
import "./index.css";
// Sistema visual V3: va después y bajo #root, para ganarle a los estilos de cada módulo.
import "./styles/sistema.css";
import { startTableLabels } from "./lib/tableLabels";

// Rótulos de columna en todas las tablas: en el celular cada fila es una tarjeta.
startTableLabels();

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
