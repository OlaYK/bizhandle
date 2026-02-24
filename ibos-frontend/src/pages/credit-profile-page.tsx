import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  PolarAngleAxis,
  PolarGrid,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";
import { dashboardService } from "../api/services";
import { Button } from "../components/ui/button";
import { Card } from "../components/ui/card";
import { EmptyState } from "../components/state/empty-state";
import { ErrorState } from "../components/state/error-state";
import { LoadingState } from "../components/state/loading-state";
import { Input } from "../components/ui/input";
import { formatCurrency, formatNumber } from "../lib/format";

function toInt(value: string, fallback: number): number {
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function toFloat(value: string, fallback: number): number {
  const parsed = Number.parseFloat(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

export function CreditProfilePage() {
  const [windowDays, setWindowDays] = useState("30");
  const [horizonDays, setHorizonDays] = useState("30");
  const [historyDays, setHistoryDays] = useState("90");
  const [intervalDays, setIntervalDays] = useState("7");
  const [targetScore, setTargetScore] = useState("80");

  const [priceChangePct, setPriceChangePct] = useState("0");
  const [expenseChangePct, setExpenseChangePct] = useState("0");
  const [restockInvestment, setRestockInvestment] = useState("0");
  const [restockReturnMultiplier, setRestockReturnMultiplier] = useState("1.2");

  const profileQuery = useQuery({
    queryKey: ["credit", "profile-v2", windowDays],
    queryFn: () =>
      dashboardService.creditProfileV2({
        window_days: toInt(windowDays, 30)
      })
  });

  const forecastQuery = useQuery({
    queryKey: ["credit", "forecast", horizonDays, historyDays, intervalDays],
    queryFn: () =>
      dashboardService.creditForecast({
        horizon_days: toInt(horizonDays, 30),
        history_days: toInt(historyDays, 90),
        interval_days: toInt(intervalDays, 7)
      })
  });

  const scenarioMutation = useMutation({
    mutationFn: () =>
      dashboardService.simulateCreditScenario({
        horizon_days: toInt(horizonDays, 30),
        history_days: toInt(historyDays, 90),
        interval_days: toInt(intervalDays, 7),
        price_change_pct: toFloat(priceChangePct, 0),
        expense_change_pct: toFloat(expenseChangePct, 0),
        restock_investment: toFloat(restockInvestment, 0),
        restock_return_multiplier: toFloat(restockReturnMultiplier, 1.2)
      })
  });

  const guardrailsQuery = useQuery({
    queryKey: ["credit", "guardrails", windowDays, historyDays, horizonDays, intervalDays],
    queryFn: () =>
      dashboardService.evaluateFinanceGuardrails({
        window_days: toInt(windowDays, 30),
        history_days: toInt(historyDays, 90),
        horizon_days: toInt(horizonDays, 30),
        interval_days: toInt(intervalDays, 7)
      })
  });

  const planQuery = useQuery({
    queryKey: ["credit", "improvement-plan", windowDays, targetScore],
    queryFn: () =>
      dashboardService.creditImprovementPlan({
        window_days: toInt(windowDays, 30),
        target_score: toInt(targetScore, 80)
      })
  });

  const exportPackMutation = useMutation({
    mutationFn: () =>
      dashboardService.generateCreditExportPack({
        window_days: toInt(windowDays, 30),
        history_days: toInt(historyDays, 120),
        horizon_days: toInt(horizonDays, 90)
      }),
    onSuccess: (pack) => {
      const blob = new Blob([JSON.stringify(pack, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `lender-pack-${pack.pack_id.slice(0, 8)}.json`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    }
  });

  if (profileQuery.isLoading || forecastQuery.isLoading || guardrailsQuery.isLoading || planQuery.isLoading) {
    return <LoadingState label="Computing credit intelligence..." />;
  }

  if (profileQuery.isError || forecastQuery.isError || guardrailsQuery.isError || planQuery.isError) {
    return (
      <ErrorState
        message="Failed to load credit intelligence data."
        onRetry={() => {
          profileQuery.refetch();
          forecastQuery.refetch();
          guardrailsQuery.refetch();
          planQuery.refetch();
        }}
      />
    );
  }

  if (!profileQuery.data || !forecastQuery.data || !guardrailsQuery.data || !planQuery.data) {
    return <EmptyState title="No credit profile data available." />;
  }

  const forecastChartData = forecastQuery.data.intervals.map((interval) => ({
    label: `W${interval.interval_index}`,
    net: interval.projected_net_cashflow,
    low: interval.net_lower_bound,
    high: interval.net_upper_bound
  }));

  const scenarioChartData = scenarioMutation.data
    ? scenarioMutation.data.baseline.intervals.map((baselineInterval, idx) => ({
        label: `W${baselineInterval.interval_index}`,
        baseline: baselineInterval.projected_net_cashflow,
        scenario: scenarioMutation.data?.scenario.intervals[idx]?.projected_net_cashflow ?? 0
      }))
    : [];

  return (
    <div className="space-y-6">
      <Card className="animate-fade-up">
        <div className="grid gap-3 sm:grid-cols-4">
          <Input
            label="Trend Window (Days)"
            type="number"
            min={14}
            max={90}
            value={windowDays}
            onChange={(event) => setWindowDays(event.target.value)}
          />
          <Input
            label="Forecast Horizon"
            type="number"
            min={7}
            max={180}
            value={horizonDays}
            onChange={(event) => setHorizonDays(event.target.value)}
          />
          <Input
            label="History Window"
            type="number"
            min={30}
            max={365}
            value={historyDays}
            onChange={(event) => setHistoryDays(event.target.value)}
          />
          <Input
            label="Interval Days"
            type="number"
            min={7}
            max={30}
            value={intervalDays}
            onChange={(event) => setIntervalDays(event.target.value)}
          />
        </div>
      </Card>

      <Card className="animate-fade-up [animation-delay:80ms] bg-[linear-gradient(135deg,#ffffff_0,#ecfff3_58%,#fffde8_100%)]">
        <p className="text-xs uppercase tracking-wide text-surface-500">Credit Intelligence 2.0</p>
        <h3 className="mt-1 font-heading text-3xl font-black text-surface-800">
          {profileQuery.data.overall_score} / 100
        </h3>
        <p className="mt-2 inline-flex rounded-full bg-surface-100 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-surface-700">
          {profileQuery.data.grade}
        </p>
        <p className="mt-2 text-xs text-surface-500">
          Current window: {profileQuery.data.current_window_start_date} to{" "}
          {profileQuery.data.current_window_end_date}
        </p>
        <p className="text-xs text-surface-500">
          Previous window: {profileQuery.data.previous_window_start_date} to{" "}
          {profileQuery.data.previous_window_end_date}
        </p>
        <div className="mt-4">
          <Button
            variant="secondary"
            loading={exportPackMutation.isPending}
            onClick={() => exportPackMutation.mutate()}
          >
            Export Lender Pack
          </Button>
          {exportPackMutation.isError ? (
            <p className="mt-2 text-xs text-red-600">Failed to generate lender pack.</p>
          ) : null}
        </div>
      </Card>

      <div className="grid gap-6 xl:grid-cols-2">
        <Card className="animate-fade-up [animation-delay:120ms]">
          <h4 className="font-heading text-lg font-bold text-surface-800">Explainable Factors</h4>
          <div className="mt-4 h-72">
            <ResponsiveContainer width="100%" height="100%">
              <RadarChart data={profileQuery.data.factors}>
                <PolarGrid />
                <PolarAngleAxis dataKey="label" tick={{ fontSize: 11, fill: "#2d4a63" }} />
                <Radar dataKey="score" stroke="#27c25c" fill="#27c25c" fillOpacity={0.35} />
              </RadarChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card className="animate-fade-up [animation-delay:160ms]">
          <h4 className="font-heading text-lg font-bold text-surface-800">Forecast With Error Bounds</h4>
          <div className="mt-4 h-72">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={forecastChartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="label" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Line type="monotone" dataKey="net" stroke="#27c25c" strokeWidth={2} />
                <Line type="monotone" dataKey="low" stroke="#f0b429" strokeDasharray="6 4" />
                <Line type="monotone" dataKey="high" stroke="#2d4a63" strokeDasharray="6 4" />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <p className="mt-3 text-xs text-surface-500">
            Forecast error bound: {forecastQuery.data.error_bound_pct}% with baseline daily net{" "}
            {formatCurrency(forecastQuery.data.baseline_daily_net)}.
          </p>
        </Card>
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <Card className="animate-fade-up [animation-delay:200ms]">
          <h4 className="font-heading text-lg font-bold text-surface-800">Current Window Totals</h4>
          <div className="mt-4 space-y-2 text-sm text-surface-600">
            <p>Net Sales: {formatCurrency(profileQuery.data.current_net_sales)}</p>
            <p>Expenses: {formatCurrency(profileQuery.data.current_expenses_total)}</p>
            <p>Net Cashflow: {formatCurrency(profileQuery.data.current_net_cashflow)}</p>
            <p>Forecast Intervals: {formatNumber(forecastQuery.data.intervals.length)}</p>
          </div>
        </Card>

        <Card className="animate-fade-up [animation-delay:240ms]">
          <h4 className="font-heading text-lg font-bold text-surface-800">Priority Recommendations</h4>
          <div className="mt-3 space-y-2">
            {profileQuery.data.recommendations.map((item) => (
              <div
                key={item}
                className="rounded-xl border border-surface-100 bg-surface-50 p-3 text-sm text-surface-700"
              >
                {item}
              </div>
            ))}
          </div>
        </Card>
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <Card className="animate-fade-up [animation-delay:260ms]">
          <h4 className="font-heading text-lg font-bold text-surface-800">Finance Guardrail Alerts</h4>
          <div className="mt-3 space-y-2">
            {guardrailsQuery.data.alerts.length === 0 ? (
              <p className="text-sm text-surface-600">No active guardrail alerts.</p>
            ) : (
              guardrailsQuery.data.alerts.map((alert) => (
                <div
                  key={`${alert.alert_type}-${alert.window_end_date}`}
                  className="rounded-xl border border-surface-100 bg-surface-50 p-3 text-sm text-surface-700"
                >
                  <p className="font-semibold uppercase tracking-wide text-xs">{alert.alert_type}</p>
                  <p className="mt-1">{alert.message}</p>
                </div>
              ))
            )}
          </div>
        </Card>

        <Card className="animate-fade-up [animation-delay:270ms]">
          <h4 className="font-heading text-lg font-bold text-surface-800">Credit Improvement Planner</h4>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            <Input
              label="Target Score"
              type="number"
              min={50}
              max={100}
              value={targetScore}
              onChange={(event) => setTargetScore(event.target.value)}
            />
          </div>
          <div className="mt-3 space-y-2">
            {planQuery.data.actions.map((action) => (
              <div
                key={`${action.factor_key}-${action.priority}`}
                className="rounded-xl border border-surface-100 bg-surface-50 p-3 text-sm text-surface-700"
              >
                <p className="font-semibold">
                  #{action.priority} {action.title} (+{action.estimated_score_impact.toFixed(1)} pts)
                </p>
                <p className="mt-1">{action.description}</p>
                <p className="mt-1 text-xs text-surface-500">{action.measurable_target}</p>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <Card className="animate-fade-up [animation-delay:280ms]">
        <h4 className="font-heading text-lg font-bold text-surface-800">Scenario Simulator</h4>
        <div className="mt-4 grid gap-3 sm:grid-cols-4">
          <Input
            label="Price Change (0.1 = 10%)"
            type="number"
            step="0.01"
            value={priceChangePct}
            onChange={(event) => setPriceChangePct(event.target.value)}
          />
          <Input
            label="Expense Change (0.1 = 10%)"
            type="number"
            step="0.01"
            value={expenseChangePct}
            onChange={(event) => setExpenseChangePct(event.target.value)}
          />
          <Input
            label="Restock Investment"
            type="number"
            step="0.01"
            value={restockInvestment}
            onChange={(event) => setRestockInvestment(event.target.value)}
          />
          <Input
            label="Restock Return Multiplier"
            type="number"
            step="0.1"
            value={restockReturnMultiplier}
            onChange={(event) => setRestockReturnMultiplier(event.target.value)}
          />
        </div>
        <div className="mt-4">
          <Button
            variant="secondary"
            loading={scenarioMutation.isPending}
            onClick={() => scenarioMutation.mutate()}
          >
            Simulate Scenario
          </Button>
        </div>
        {scenarioMutation.isError ? (
          <p className="mt-3 text-sm text-red-600">Scenario simulation failed. Try again.</p>
        ) : null}
      </Card>

      {scenarioMutation.data ? (
        <div className="grid gap-6 xl:grid-cols-2">
          <Card className="animate-fade-up [animation-delay:320ms]">
            <h4 className="font-heading text-lg font-bold text-surface-800">Baseline vs Scenario</h4>
            <div className="mt-4 space-y-2 text-sm text-surface-600">
              <p>Baseline Net: {formatCurrency(scenarioMutation.data.baseline.projected_net_cashflow)}</p>
              <p>Scenario Net: {formatCurrency(scenarioMutation.data.scenario.projected_net_cashflow)}</p>
              <p>Net Delta: {formatCurrency(scenarioMutation.data.delta.net_cashflow_delta)}</p>
              <p>Revenue Delta: {formatCurrency(scenarioMutation.data.delta.revenue_delta)}</p>
              <p>Expense Delta: {formatCurrency(scenarioMutation.data.delta.expenses_delta)}</p>
              <p>Margin Delta: {scenarioMutation.data.delta.margin_delta_pct.toFixed(2)}%</p>
            </div>
          </Card>

          <Card className="animate-fade-up [animation-delay:360ms]">
            <h4 className="font-heading text-lg font-bold text-surface-800">Scenario Interval Comparison</h4>
            <div className="mt-4 h-72">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={scenarioChartData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="label" />
                  <YAxis />
                  <Tooltip />
                  <Legend />
                  <Line type="monotone" dataKey="baseline" stroke="#2d4a63" strokeWidth={2} />
                  <Line type="monotone" dataKey="scenario" stroke="#27c25c" strokeWidth={2} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </Card>
        </div>
      ) : null}
    </div>
  );
}
