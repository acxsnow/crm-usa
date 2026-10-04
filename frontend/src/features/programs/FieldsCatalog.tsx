import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useAuth } from "@/features/auth/AuthContext";
import { apiErrorMessage } from "@/features/field-ops/module5Api";
import type { FieldDefinition, FieldOption } from "@/types/programs";
import { createField, listFields, programKeys, updateField, useProgramCatalogs } from "./api";

/**
 * Catálogo de campos (§2.4): cada pregunta existe una vez y los programas la
 * reutilizan. La clave y el tipo no cambian; para "borrar" se desactiva.
 */
export function FieldsCatalog() {
  const { hasPermission } = useAuth();
  const puede = hasPermission("fields.manage");
  const { data: campos } = useQuery({ queryKey: programKeys.fields, queryFn: listFields });
  const { data: cat } = useProgramCatalogs();
  const [buscar, setBuscar] = useState("");
  const [abierto, setAbierto] = useState<string | null>(null);
  const [nuevo, setNuevo] = useState(false);

  const grupos = useMemo(() => {
    const q = buscar.trim().toLowerCase();
    const filtrados = (campos ?? []).filter((c) => !q || c.label.toLowerCase().includes(q) || c.key.includes(q));
    const m = new Map<string, FieldDefinition[]>();
    for (const c of filtrados) m.set(c.section ?? "Sin sección", [...(m.get(c.section ?? "Sin sección") ?? []), c]);
    return [...m.entries()];
  }, [campos, buscar]);

  return (
    <section className="acta billing-list" aria-label="Catálogo de campos">
      <header className="acta-header">
        <div className="acta-title-row">
          <h2 className="acta-title">Catálogo de campos</h2>
          {puede && !nuevo && <button type="button" className="acta-btn is-primary" onClick={() => setNuevo(true)}>Nuevo campo</button>}
        </div>
        <p className="acta-lead">{(campos ?? []).length} preguntas. La clave interna no cambia aunque cambie la etiqueta:
          reportes, documentos y facturas se apoyan en ella.</p>
      </header>
      {nuevo && <NewField onDone={() => setNuevo(false)} />}
      <input className="catalog-search" type="search" placeholder="Buscar por etiqueta o clave" value={buscar}
        onChange={(e) => setBuscar(e.target.value)} aria-label="Buscar campo" />
      {grupos.map(([seccion, lista]) => (
        <div key={seccion} className="catalog-group">
          <h3>{seccion}</h3>
          <ul className="invoice-rows">
            {lista.map((c) => (
              <li key={c.id} className={abierto === c.id ? "is-open" : undefined}>
                <button type="button" className="catalog-row" aria-expanded={abierto === c.id}
                  onClick={() => setAbierto(abierto === c.id ? null : c.id)}>
                  <span className="invoice-row-main"><strong className={c.active ? undefined : "is-off"}>{c.label}</strong>
                    <span className="money">{c.key}</span></span>
                  <span className="catalog-type">{cat?.field_types[c.field_type] ?? c.field_type}</span>
                  <span className="catalog-flags">
                    {c.binding && <span className="form-tag">→ {cat?.bindings[c.binding] ?? c.binding}</span>}
                    {c.internal && <span className="form-tag">uso interno</span>}
                    {c.sensitive && <span className="form-tag is-sensitive">sensible</span>}
                    {!c.active && <span className="form-tag">desactivado</span>}
                  </span>
                  <span className="invoice-row-caret" aria-hidden="true">›</span>
                </button>
                {abierto === c.id && <EditField field={c} editable={puede} />}
              </li>
            ))}
          </ul>
        </div>
      ))}
    </section>
  );
}

function OptionsEditor({ options, onChange }: { options: FieldOption[]; onChange: (o: FieldOption[]) => void }) {
  return (
    <div className="options-editor">
      {options.map((o, i) => (
        <div key={i} className="options-row">
          <input aria-label="Valor" value={o.value} placeholder="valor_interno"
            onChange={(e) => onChange(options.map((x, n) => (n === i ? { ...x, value: e.target.value } : x)))} />
          <input aria-label="Etiqueta" value={o.label} placeholder="Lo que ve el vendedor"
            onChange={(e) => onChange(options.map((x, n) => (n === i ? { ...x, label: e.target.value } : x)))} />
        </div>
      ))}
      <button type="button" className="acta-btn is-line" onClick={() => onChange([...options, { value: "", label: "" }])}>+ Opción</button>
    </div>
  );
}

function EditField({ field, editable }: { field: FieldDefinition; editable: boolean }) {
  const qc = useQueryClient();
  const [f, setF] = useState(field);
  const [error, setError] = useState<string | null>(null);
  const guardar = useMutation({
    mutationFn: () => updateField(field.id, { label: f.label, help_text: f.help_text, section: f.section,
      options: f.options, internal: f.internal, sensitive: f.sensitive, active: f.active }),
    onSuccess: () => { setError(null); return qc.invalidateQueries({ queryKey: programKeys.fields }); },
    onError: (e) => setError(apiErrorMessage(e)),
  });
  const conOpciones = ["single_select", "multi_select"].includes(field.field_type);
  return (
    <form className="program-inline-form catalog-edit" onSubmit={(e) => { e.preventDefault(); guardar.mutate(); }}>
      {error && <p className="form-error program-span">{error}</p>}
      <fieldset disabled={!editable} className="program-span catalog-fieldset">
        <div className="field"><label htmlFor={`fl-${field.id}`}>Etiqueta</label>
          <input id={`fl-${field.id}`} value={f.label} onChange={(e) => setF({ ...f, label: e.target.value })} /></div>
        <div className="field"><label htmlFor={`fs-${field.id}`}>Sección</label>
          <input id={`fs-${field.id}`} value={f.section ?? ""} onChange={(e) => setF({ ...f, section: e.target.value })} /></div>
        <div className="field program-span"><label htmlFor={`fh-${field.id}`}>Ayuda para el vendedor</label>
          <input id={`fh-${field.id}`} value={f.help_text ?? ""} onChange={(e) => setF({ ...f, help_text: e.target.value })} /></div>
        {conOpciones && (
          <div className="field program-span"><label>Opciones (las ya usadas no se quitan; se les cambia la etiqueta)</label>
            <OptionsEditor options={f.options ?? []} onChange={(o) => setF({ ...f, options: o })} /></div>
        )}
        <label className="billing-check"><input type="checkbox" checked={f.internal} onChange={(e) => setF({ ...f, internal: e.target.checked })} /> Uso interno (no lo ve el cliente)</label>
        <label className="billing-check"><input type="checkbox" checked={f.sensitive} onChange={(e) => setF({ ...f, sensitive: e.target.checked })} /> Dato sensible</label>
        <label className="billing-check"><input type="checkbox" checked={f.active} onChange={(e) => setF({ ...f, active: e.target.checked })} /> Activo</label>
      </fieldset>
      {editable && <div className="acta-actions program-span"><button type="submit" className="acta-btn is-primary" disabled={guardar.isPending}>Guardar</button></div>}
    </form>
  );
}

function NewField({ onDone }: { onDone: () => void }) {
  const qc = useQueryClient();
  const { data: cat } = useProgramCatalogs();
  const [f, setF] = useState({ key: "", label: "", field_type: "text", section: "", help_text: "", binding: "",
    internal: false, sensitive: false, options: [] as FieldOption[] });
  const [error, setError] = useState<string | null>(null);
  const crear = useMutation({
    mutationFn: () => createField({ ...f, binding: f.binding || null, section: f.section || null,
      help_text: f.help_text || null, options: f.options.length ? f.options : null }),
    onSuccess: async () => { await qc.invalidateQueries({ queryKey: programKeys.fields }); onDone(); },
    onError: (e) => setError(apiErrorMessage(e)),
  });
  return (
    <form className="program-inline-form" onSubmit={(e) => { e.preventDefault(); crear.mutate(); }}>
      {error && <p className="form-error program-span">{error}</p>}
      <div className="field"><label htmlFor="nf-label">Etiqueta</label>
        <input id="nf-label" required value={f.label} onChange={(e) => setF({ ...f, label: e.target.value })} placeholder="¿Tiene mascotas?" autoFocus /></div>
      <div className="field"><label htmlFor="nf-key">Clave (no cambia)</label>
        <input id="nf-key" required value={f.key} onChange={(e) => setF({ ...f, key: e.target.value.toLowerCase() })} placeholder="home.pets" /></div>
      <div className="field"><label htmlFor="nf-type">Tipo</label>
        <select id="nf-type" value={f.field_type} onChange={(e) => setF({ ...f, field_type: e.target.value })}>
          {Object.entries(cat?.field_types ?? {}).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></div>
      <div className="field"><label htmlFor="nf-sec">Sección</label>
        <input id="nf-sec" value={f.section} onChange={(e) => setF({ ...f, section: e.target.value })} placeholder="Vivienda" /></div>
      <div className="field"><label htmlFor="nf-bind">Guardar también en</label>
        <select id="nf-bind" value={f.binding} onChange={(e) => setF({ ...f, binding: e.target.value })}>
          <option value="">Solo en el formulario</option>
          {Object.entries(cat?.bindings ?? {}).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></div>
      {["single_select", "multi_select"].includes(f.field_type) && (
        <div className="field program-span"><label>Opciones</label>
          <OptionsEditor options={f.options} onChange={(o) => setF({ ...f, options: o })} /></div>
      )}
      <label className="billing-check"><input type="checkbox" checked={f.internal} onChange={(e) => setF({ ...f, internal: e.target.checked })} /> Uso interno</label>
      <label className="billing-check"><input type="checkbox" checked={f.sensitive} onChange={(e) => setF({ ...f, sensitive: e.target.checked })} /> Dato sensible</label>
      <div className="acta-actions">
        <button type="button" className="acta-btn is-quiet" onClick={onDone}>Cancelar</button>
        <button type="submit" className="acta-btn is-primary" disabled={crear.isPending}>Crear campo</button>
      </div>
    </form>
  );
}
