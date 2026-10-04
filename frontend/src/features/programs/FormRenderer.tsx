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
export function FormRenderer({ evaluation, answers, onChange, stepCode, mediaPlaceholder = false }: {
  evaluation: Evaluation;
  answers: Answers;
  onChange: (key: string, value: unknown) => void;
  stepCode?: string;
  mediaPlaceholder?: boolean;
}) {
  const pasos = stepCode ? evaluation.steps.filter((s) => s.code === stepCode) : evaluation.steps;
  return (
    <div className="form-renderer">
      {pasos.map((paso) => (
        <fieldset key={paso.code} className="form-step">
          <legend>{paso.title}</legend>
          {paso.fields.length === 0 && <p className="acta-empty">Nada que responder en este paso con lo elegido.</p>}
          {paso.fields.map((f) => (
            <FieldControl key={f.key} field={f} value={answers[f.key]} onChange={(v) => onChange(f.key, v)}
              mediaPlaceholder={mediaPlaceholder} showMissing={false} />
          ))}
        </fieldset>
      ))}
    </div>
  );
}

const MEDIA = { photo: "Tomar foto", document: "Subir documento", video: "Grabar video", signature: "Firmar en pantalla" } as const;

function FieldControl({ field: f, value, onChange, mediaPlaceholder, showMissing }: {
  field: EvaluatedField; value: unknown; onChange: (v: unknown) => void; mediaPlaceholder: boolean; showMissing: boolean;
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
    case "decimal":
      control = <input id={id} type="number" inputMode={f.type === "integer" ? "numeric" : "decimal"}
        step={f.type === "integer" ? 1 : "any"} value={String(texto)}
        onChange={(e) => onChange(e.target.value === "" ? "" : Number(e.target.value))} />;
      break;
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
    case "photo":
    case "document":
    case "video":
    case "signature":
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
      control = <p className="form-system">{f.type === "system_user" ? "Se llena con el usuario que envía" : f.type === "system_datetime" ? "Se llena solo al firmar" : f.help}</p>;
      break;
    default:
      control = <input id={id} type="text" value={String(texto)} onChange={(e) => onChange(e.target.value)} />;
  }

  return (
    <div className={`form-field${f.error ? " has-error" : ""}${showMissing && f.missing ? " is-missing" : ""}`}>
      {etiqueta}
      {control}
      {ayuda}
      {error}
    </div>
  );
}
