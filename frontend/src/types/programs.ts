/** Módulo 1: programas, catálogo de campos, flujo versionado y zonas de venta. */

export interface Program {
  id: string;
  code: string;
  name: string;
  active: boolean;
  description: string | null;
  funder_name: string | null;
  customer_facing_name: string | null;
  logo_url: string | null;
  authorization_text: string | null;
  invoice_entity: string | null;
  published_version: string | null;
}

export interface ProgramTerms {
  id: string;
  program_id: string;
  version: string;
  language: string;
  title: string;
  body: string;
  published_at: string | null;
}

export interface FieldOption { value: string; label: string }

export interface FieldDefinition {
  id: string;
  key: string;
  label: string;
  field_type: string;
  help_text: string | null;
  section: string | null;
  options: FieldOption[] | null;
  validation: Record<string, unknown> | null;
  binding: string | null;
  internal: boolean;
  sensitive: boolean;
  active: boolean;
}

export type VersionStatus = "draft" | "published" | "archived";

export interface ProgramVersion {
  id: string;
  program_id: string;
  version: string;
  status: VersionStatus;
  published_at: string | null;
  terms_id: string | null;
  notes: string | null;
  created_at: string;
}

export interface Condition { field: string; eq?: unknown; in?: unknown[]; not_empty?: boolean }

/** Un campo ya resuelto dentro de un paso (lo que evalúa el motor). */
export interface DefinitionField {
  id: string;
  field_id: string;
  key: string;
  label: string;
  help: string | null;
  type: string;
  options: FieldOption[] | null;
  validation: Record<string, unknown> | null;
  binding: string | null;
  requirement: "required" | "optional" | "conditional";
  condition: Condition | null;
  internal: boolean;
  sensitive: boolean;
}

export interface DefinitionStep {
  id: string;
  code: string;
  title: string;
  description: string | null;
  phase: string;
  phase_name: string;
  role: string;
  fields: DefinitionField[];
}

export interface VersionDetail {
  version: ProgramVersion;
  phases: { id: string; code: string; name: string; role_code: string;
    steps: { id: string; code: string; title: string; description: string | null }[] }[];
  definition: { steps: DefinitionStep[] };
  problems: string[];
}

export interface EvaluatedField extends DefinitionField { error: string | null; missing: boolean }

export interface Evaluation {
  steps: { code: string; title: string; phase: string; fields: EvaluatedField[]; complete: boolean }[];
  missing: { step: string; key: string; label: string }[];
  errors: Record<string, string>;
  can_submit: boolean;
}

export interface Zone {
  id: string;
  program_id: string | null;
  code: string;
  name: string;
  state: string | null;
  city: string | null;
  notes: string | null;
  active: boolean;
  salesperson_ids: string[];
}

export interface ProgramCatalogs {
  field_types: Record<string, string>;
  bindings: Record<string, string>;
  requirements: Record<string, string>;
  phase_roles: Record<string, string>;
  languages: Record<string, string>;
}
