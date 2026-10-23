import { useState, type FormEvent } from "react";

export type FilterFieldDef =
  | { key: string; label: string; type: "text"; placeholder?: string }
  | { key: string; label: string; type: "select"; options: { value: string; label: string }[] };

interface FilterBarProps {
  fields: FilterFieldDef[];
  values: Record<string, string>;
  onApply: (values: Record<string, string>) => void;
  onClear: () => void;
}

export function FilterBar({ fields, values, onApply, onClear }: FilterBarProps) {
  const [draft, setDraft] = useState<Record<string, string>>(values);
  const [open, setOpen] = useState(true);

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    onApply(draft);
  }

  function handleClear() {
    setDraft({});
    onClear();
  }

  return (
    <form className="filter-bar" onSubmit={handleSubmit}>
      <button type="button" className="filter-bar-toggle" onClick={() => setOpen((o) => !o)}>
        {open ? "▾" : "▸"} Filtros
      </button>
      {open && (
        <>
          <div className="filter-bar-fields">
            {fields.map((field) => (
              <label key={field.key} className="filter-bar-field">
                <span>{field.label}</span>
                {field.type === "text" ? (
                  <input
                    type="text"
                    placeholder={field.placeholder}
                    value={draft[field.key] ?? ""}
                    onChange={(e) => setDraft((d) => ({ ...d, [field.key]: e.target.value }))}
                  />
                ) : (
                  <select
                    value={draft[field.key] ?? ""}
                    onChange={(e) => setDraft((d) => ({ ...d, [field.key]: e.target.value }))}
                  >
                    <option value="">Todos</option>
                    {field.options.map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </select>
                )}
              </label>
            ))}
          </div>
          <div className="filter-bar-actions">
            <button type="submit" className="primary-button">
              Buscar
            </button>
            <button type="button" className="link-button" onClick={handleClear}>
              Limpiar
            </button>
          </div>
        </>
      )}
    </form>
  );
}
