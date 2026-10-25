import React from "react";
import ReactDOM from "react-dom/client";
import { App } from "./App";
import "./index.css";
// Sistema visual V3: va después y bajo #root, para ganarle a los estilos de cada módulo.
import "./styles/sistema.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
