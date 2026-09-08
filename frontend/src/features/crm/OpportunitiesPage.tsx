import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { changeOpportunityStage, listFunderStatuses, listOpportunities, listPipelineStages, updateOpportunityFunderStatus } from "./api";
import type { Opportunity } from "@/types/crm";

export function OpportunitiesPage() {
  const queryClient = useQueryClient();
  const { data: stages, isLoading: stagesLoading } = useQuery({ queryKey: ["pipeline-stages"], queryFn: listPipelineStages });
  const { data: opportunities, isLoading: oppsLoading } = useQuery({ queryKey: ["opportunities"], queryFn: listOpportunities });
  const { data: funderStatuses } = useQuery({ queryKey: ["funder-statuses"], queryFn: listFunderStatuses });

  const stageMutation = useMutation({
    mutationFn: ({ id, stageCode }: { id: string; stageCode: string }) => changeOpportunityStage(id, stageCode),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["opportunities"] }),
  });

  const funderStatusMutation = useMutation({
    mutationFn: ({ id, code }: { id: string; code: string }) => updateOpportunityFunderStatus(id, code),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["opportunities"] }),
  });

  if (stagesLoading || oppsLoading) return <p>Cargando...</p>;

  const sortedStages = [...(stages ?? [])].sort((a, b) => a.sort_order - b.sort_order);
  const byStage = new Map<string, Opportunity[]>();
  for (const opp of opportunities ?? []) {
    const list = byStage.get(opp.stage.code) ?? [];
    list.push(opp);
    byStage.set(opp.stage.code, list);
  }

  return (
    <div>
      <h1>Pipeline de oportunidades</h1>
      <div className="pipeline-board">
        {sortedStages.map((stage) => (
          <div key={stage.id} className="pipeline-column">
            <h3>
              {stage.name} <span className="pipeline-count">{byStage.get(stage.code)?.length ?? 0}</span>
            </h3>
            {(byStage.get(stage.code) ?? []).map((opp) => (
              <div key={opp.id} className="pipeline-card">
                <strong>{opp.title}</strong>
                <div className="pipeline-card-meta">
                  {opp.funder_program} {opp.benefit_type && `· ${opp.benefit_type}`}
                </div>
                <div className="pipeline-card-meta">
                  {[opp.address_street, opp.address_unit].filter(Boolean).join(", ")}
                </div>
                {opp.funder_status && (
                  <span className="status-pill">{opp.funder_status.name}</span>
                )}
                <select
                  value={stage.code}
                  onChange={(e) => stageMutation.mutate({ id: opp.id, stageCode: e.target.value })}
                >
                  {sortedStages.map((s) => (
                    <option key={s.code} value={s.code}>
                      {s.name}
                    </option>
                  ))}
                </select>
                {funderStatuses && funderStatuses.length > 0 && (
                  <select
                    value={opp.funder_status?.code ?? ""}
                    onChange={(e) => e.target.value && funderStatusMutation.mutate({ id: opp.id, code: e.target.value })}
                  >
                    <option value="" disabled>
                      Estado del programa...
                    </option>
                    {funderStatuses.map((fs) => (
                      <option key={fs.code} value={fs.code}>
                        {fs.name}
                      </option>
                    ))}
                  </select>
                )}
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
