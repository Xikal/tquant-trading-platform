import { BacktestDashboard } from "./BacktestDashboard";
import { useBacktestDashboard } from "./useBacktestDashboard";

export function BacktestPage() {
  const dashboard = useBacktestDashboard();

  return (
    <BacktestDashboard
      form={dashboard.form}
      runs={dashboard.runs}
      selectedRun={dashboard.selectedRun}
      equity={dashboard.equity}
      trades={dashboard.trades}
      loading={dashboard.loading}
      error={dashboard.error}
      notice={dashboard.notice}
      research={dashboard.research}
      researchActions={dashboard.researchActions}
      onFormChange={dashboard.onFormChange}
      onToggleStrategy={dashboard.onToggleStrategy}
      onSubmit={dashboard.submit}
      onRefresh={() => void dashboard.loadRuns()}
      onSelectRun={dashboard.selectRun}
      onCancelRun={dashboard.cancelRun}
    />
  );
}
