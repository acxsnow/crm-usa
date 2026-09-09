import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { listApplications, updateApplication } from "./api";

export function ApplicationsAdminPage() {
  const client = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["applications"], queryFn: listApplications });
  const mutation = useMutation({ mutationFn: ({ id, status }: { id: string; status: string }) => updateApplication(id, { status }), onSuccess: () => client.invalidateQueries({ queryKey: ["applications"] }) });
  if (isLoading) return <p>Cargando...</p>;
  return <div className="list-page"><div className="page-heading"><div><p className="eyebrow">CONTROL ADMINISTRATIVO</p><h1>Aplicaciones</h1><p className="page-subtitle">Revisa la documentación antes de someter cada caso al programa.</p></div></div><div className="table-wrap"><table className="data-table"><thead><tr><th>Programa</th><th>Estado</th><th>Creada</th><th>Revisión</th></tr></thead><tbody>{(data ?? []).map((app) => <tr key={app.id}><td><strong>{app.program_code}</strong><br /><small>{app.id.slice(0, 8)}</small></td><td><span className="status-pill">{app.status.split("_").join(" ")}</span></td><td>{new Date(app.created_at).toLocaleDateString("es-CO")}</td><td><select value={app.status} onChange={(e) => mutation.mutate({ id: app.id, status: e.target.value })}><option value="pending_review">Pendiente de revisión</option><option value="correction_requested">Solicitar corrección</option><option value="ready_to_submit">Lista para someter</option><option value="submitted">Sometida</option><option value="approved">Aprobada</option><option value="rejected">Rechazada</option></select></td></tr>)}</tbody></table></div></div>;
}
