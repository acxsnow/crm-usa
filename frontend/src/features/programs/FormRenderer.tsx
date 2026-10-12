import { useState } from "react";

import type { Evaluation, EvaluatedField } from "@/types/programs";

type Answers = Record<string, unknown>;

/**
 * Dibuja cualquier paso del formulario de un programa a partir de lo que
 * devuelve el motor (`engine.evaluate`): solo los campos visibles, con su
 * error y lo que falta. Una sola pantalla para los 18 tipos de campo, sin
 * programar un formulario por paso (módulo 1 vista previa, módulo 2 vendedor).
 *
 * `mediaPlaceholder`: en la vista previa, fotos, documentos, videos y firma se
 * muestran como el control que verá el vendedor, sin subir nada.
 */
export interface MediaSupport {
  /** Sube el archivo del campo y devuelve su id (lo que se guarda como respuesta). */
  upload: (fieldKey: string, file: File) => Promise<string>;
  /** Nombre visible de un archivo ya subido. */
  fileName: (fileId: string) => string | undefined;
  /** Abre el archivo (para revisarlo antes de enviar). */
  open?: (fileId: string) => void;
}

export function FormRenderer({ evaluation, answers, onChange, stepCode, mediaPlaceholder = false, media,
  showMissing = false, disabled = false }: {
  evaluation: Evaluation;
  answers: Answers;
  onChange: (key: string, value: unknown) => void;
  stepCode?: string;
  mediaPlaceholder?: boolean;
  media?: MediaSupport;
  showMissing?: boolean;
  disabled?: boolean;
}) {
  const pasos = stepCode ? evaluation.steps.filter((s) => s.code === stepCode) : evaluation.steps;
  return (
    <div className="form-renderer">
      {pasos.map((paso) => (
        paso.fields.length === 0 && paso.title === "Otros datos" ? null :
        <fieldset key={paso.code} className="form-step">
          <legend>{paso.title}</legend>
          {paso.fields.length === 0 && <p className="acta-empty">Nada que responder en este paso con lo elegido.</p>}
          {paso.fields.map((f) => (
            <FieldControl key={f.key} field={f} value={answers[f.key]} onChange={(v) => onChange(f.key, v)}
              mediaPlaceholder={mediaPlaceholder} showMissing={showMissing} media={media} disabled={disabled} />
          ))}
        </fieldset>
      ))}
    </div>
  );
}

const MEDIA = { photo: "Tomar foto", document: "Subir documento", video: "Grabar video", signature: "Firmar en pantalla" } as const;

function FieldControl({ field: f, value, onChange, mediaPlaceholder, showMissing, media, disabled }: {
  field: EvaluatedField; value: unknown; onChange: (v: unknown) => void; mediaPlaceholder: boolean; showMissing: boolean;
  media?: MediaSupport; disabled: boolean;
}) {
  const id = `f-${f.key}`;
  const obligatorio = f.requirement !== "optional";
  const etiqueta = (
    <label htmlFor={id} className="form-label">
      {f.label}
      {obligatorio && <span className="form-req" aria-label="obligatorio"> *</span>}
      {f.internal && <span className="form-tag">uso interno</span>}
      {f.sensitive && <span className="form-tag is-sensitive">dato sensible</span>}
    </label>
  );
  const ayuda = f.help && <small className="form-help">{f.help}</small>;
  const error = f.error && <small className="form-error-text" role="alert">{f.error}</small>;
  const opciones = f.options ?? [];
  const texto = (value as string | number | undefined) ?? "";

  let control: JSX.Element;
  switch (f.type) {
    case "textarea":
      control = <textarea id={id} value={String(texto)} onChange={(e) => onChange(e.target.value)} />;
      break;
    case "integer":
    case "decimal": {
      // Texto con teclado numérico y no `type="number"`: ese deja escribir «e»,
      // «+» y «-» (notación científica) y cualquier tamaño. Aquí solo entran
      // dígitos (y un punto en decimales, un «-» si el mínimo es negativo) y no
      // se puede pasar del máximo configurado; el mínimo lo avisa la validación.
      const reglas = f.validation ?? {};
      const max = typeof reglas.max === "number" ? reglas.max : null;
      const negativo = typeof reglas.min === "number" && reglas.min < 0;
      const patron = f.type === "integer" ? (negativo ? /^-?\d*$/ : /^\d*$/) : (negativo ? /^-?\d*\.?\d*$/ : /^\d*\.?\d*$/);
      control = <input id={id} type="text" inputMode={f.type === "integer" ? "numeric" : "decimal"} value={String(texto)}
        onChange={(e) => {
          const v = e.target.value.trim();
          if (!patron.test(v)) return;
          if (v === "" || v === "-" || v.endsWith(".")) { onChange(v === "" ? "" : v); return; }
          const n = Number(v);
          if (max !== null && n > max) return;
          onChange(n);
        }} />;
      break;
    }
    case "phone":
      control = <input id={id} type="tel" inputMode="tel" autoComplete="tel" value={String(texto)} onChange={(e) => onChange(e.target.value)} />;
      break;
    case "email":
      control = <input id={id} type="email" inputMode="email" autoComplete="email" value={String(texto)} onChange={(e) => onChange(e.target.value)} />;
      break;
    case "date":
    case "time":
      control = <input id={id} type={f.type} value={String(texto)} onChange={(e) => onChange(e.target.value)} />;
      break;
    case "yes_no":
    case "single_select": {
      const lista = f.type === "yes_no" ? [{ value: "yes", label: "Sí" }, { value: "no", label: "No" }] : opciones;
      control = lista.length <= 4 ? (
        <div className="form-choices" role="radiogroup" aria-labelledby={id}>
          {lista.map((o) => (
            <label key={o.value} className={`form-choice${value === o.value ? " is-on" : ""}`}>
              <input type="radio" name={id} checked={value === o.value} onChange={() => onChange(o.value)} />
              {o.label}
            </label>
          ))}
        </div>
      ) : (
        <select id={id} value={String(texto)} onChange={(e) => onChange(e.target.value)}>
          <option value="">Elige…</option>
          {lista.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
      );
      break;
    }
    case "multi_select": {
      const elegidos = Array.isArray(value) ? (value as string[]) : [];
      control = (
        <div className="form-choices is-multi" id={id}>
          {opciones.map((o) => {
            const on = elegidos.includes(o.value);
            return (
              <label key={o.value} className={`form-choice${on ? " is-on" : ""}`}>
                <input type="checkbox" checked={on}
                  onChange={() => onChange(on ? elegidos.filter((v) => v !== o.value) : [...elegidos, o.value])} />
                {o.label}
              </label>
            );
          })}
        </div>
      );
      break;
    }
    case "terms_checkbox":
      control = (
        <label className={`form-choice is-terms${value === true ? " is-on" : ""}`}>
          <input id={id} type="checkbox" checked={value === true} onChange={(e) => onChange(e.target.checked)} />
          Acepto
        </label>
      );
      break;
    case "signature":
      control = !mediaPlaceholder ? (
        <p className="form-system">{value ? "✓ Firmado" : "El cliente firma en el paso de autorización, al aceptar los términos."}</p>
      ) : (
        <button type="button" id={id} className={`form-media${value ? " is-on" : ""}`} onClick={() => onChange(value ? "" : "(simulado)")}>
          {value ? "✓ Listo" : MEDIA.signature}<small>{value ? "Toca para quitar" : "En la vista previa solo se simula"}</small>
        </button>
      );
      break;
    case "photo":
    case "document":
    case "video":
      if (media && !mediaPlaceholder) {
        control = <MediaInput id={id} type={f.type} value={value as string | undefined} media={media} fieldKey={f.key}
          disabled={disabled} onChange={onChange} />;
        break;
      }
      control = (
        <button type="button" id={id} className={`form-media${value ? " is-on" : ""}`}
          onClick={() => mediaPlaceholder && onChange(value ? "" : "(simulado)")}>
          {value ? "✓ Listo" : MEDIA[f.type]}
          {mediaPlaceholder && <small>{value ? "Toca para quitar" : "En la vista previa solo se simula"}</small>}
        </button>
      );
      break;
    case "system_datetime":
    case "system_user":
    case "info":
      control = <p className="form-system">{f.type === "system_datetime" && value
        ? new Date(String(value)).toLocaleString("es-CO", { dateStyle: "long", timeStyle: "short" })
        : f.type === "system_user" ? "Se llena con el usuario que envía" : f.type === "system_datetime" ? "Se llena solo al firmar" : f.help}</p>;
      break;
    default:
      control = <input id={id} type="text" value={String(texto)} onChange={(e) => onChange(e.target.value)} />;
  }

  return (
    <div className={`form-field${f.error ? " has-error" : ""}${showMissing && f.missing ? " is-missing" : ""}`}
      aria-disabled={disabled || undefined}>
      {etiqueta}
      {control}
      {ayuda}
      {error}
    </div>
  );
}


const ACCEPT = { photo: "image/*", document: "image/*,application/pdf", video: "video/*" } as const;

/** Foto, documento o video: abre la cámara del teléfono (o el selector) y
 * sube el archivo en el momento; la respuesta guarda su id. */
function MediaInput({ id, type, value, media, fieldKey, disabled, onChange }: {
  id: string; type: "photo" | "document" | "video"; value: string | undefined; media: MediaSupport; fieldKey: string;
  disabled: boolean; onChange: (v: unknown) => void;
}) {
  const [subiendo, setSubiendo] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const nombre = value ? media.fileName(value) : undefined;
  const elegir = async (file: File | undefined) => {
    if (!file) return;
    setSubiendo(true);
    setError(null);
    try {
      onChange(await media.upload(fieldKey, file));
    } catch (e) {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(detail ?? "No se pudo subir el archivo. Revisa la señal e intenta de nuevo.");
    } finally {
      setSubiendo(false);
    }
  };
  return (
    <div className="form-media-wrap">
      <label className={`form-media${value ? " is-on" : ""}${disabled ? " is-disabled" : ""}`}>
        <input id={id} type="file" className="visually-hidden" accept={ACCEPT[type]} disabled={disabled || subiendo}
          {...(type === "photo" ? { capture: "environment" as const } : {})}
          onChange={(e) => { elegir(e.target.files?.[0]); e.target.value = ""; }} />
        {subiendo ? "Subiendo…" : value ? `✓ ${nombre ?? "Archivo listo"}` : MEDIA[type]}
        <small>{value ? "Toca para reemplazar" : type === "photo" ? "Se marca con GPS, fecha y hora" : "Imagen o PDF"}</small>
      </label>
      {value && media.open && <button type="button" className="acta-btn is-quiet" onClick={() => media.open!(value)}>Ver</button>}
      {error && <small className="form-error-text" role="alert">{error}</small>}
    </div>
  );
}
