import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bot, CheckCheck, DatabaseZap, Sparkles, X } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import type { AIResponseOut } from "../api/types";
import { aiService } from "../api/services";
import { EmptyState } from "../components/state/empty-state";
import { Button } from "../components/ui/button";
import { Card } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { Select } from "../components/ui/select";
import { Textarea } from "../components/ui/textarea";
import { useToast } from "../hooks/use-toast";
import { getApiErrorMessage } from "../lib/api-error";
import { formatCurrency, formatNumber } from "../lib/format";

const askSchema = z.object({
  question: z.string().min(3, "Enter at least 3 characters")
});

type AskFormData = z.infer<typeof askSchema>;

export function InsightsPage() {
  const { showToast } = useToast();
  const queryClient = useQueryClient();
  const [responses, setResponses] = useState<AIResponseOut[]>([]);
  const [windowDays, setWindowDays] = useState(30);
  const form = useForm<AskFormData>({
    resolver: zodResolver(askSchema),
    defaultValues: {
      question: ""
    }
  });

  const askMutation = useMutation({
    mutationFn: aiService.ask,
    onSuccess: (response) => {
      setResponses((prev) => [response, ...prev]);
      form.reset({ question: "" });
      showToast({
        title: "Insight generated",
        variant: "success"
      });
    },
    onError: (error) => {
      showToast({
        title: "AI request failed",
        description: getApiErrorMessage(error),
        variant: "error"
      });
    }
  });

  const dailyMutation = useMutation({
    mutationFn: aiService.dailyInsight,
    onSuccess: (response) => {
      setResponses((prev) => [response, ...prev]);
      showToast({
        title: "Daily insight ready",
        variant: "success"
      });
    },
    onError: (error) => {
      showToast({
        title: "Daily insight failed",
        description: getApiErrorMessage(error),
        variant: "error"
      });
    }
  });

  const featureStoreQuery = useQuery({
    queryKey: ["ai", "feature-store", "latest"],
    queryFn: aiService.latestFeatureStore,
    retry: false
  });

  const insightsV2Query = useQuery({
    queryKey: ["ai", "insights", "v2"],
    queryFn: () => aiService.listInsightsV2()
  });

  const actionsQuery = useQuery({
    queryKey: ["ai", "actions"],
    queryFn: () => aiService.listActions()
  });

  const refreshFeatureStoreMutation = useMutation({
    mutationFn: () => aiService.refreshFeatureStore({ window_days: windowDays }),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["ai", "feature-store"] }),
        queryClient.invalidateQueries({ queryKey: ["ai", "insights", "v2"] }),
        queryClient.invalidateQueries({ queryKey: ["ai", "actions"] })
      ]);
      showToast({
        title: "Feature store refreshed",
        variant: "success"
      });
    },
    onError: (error) => {
      showToast({
        title: "Feature refresh failed",
        description: getApiErrorMessage(error),
        variant: "error"
      });
    }
  });

  const generateInsightsV2Mutation = useMutation({
    mutationFn: () => aiService.generateInsightsV2({ window_days: windowDays }),
    onSuccess: async (payload) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["ai", "feature-store"] }),
        queryClient.invalidateQueries({ queryKey: ["ai", "insights", "v2"] }),
        queryClient.invalidateQueries({ queryKey: ["ai", "actions"] })
      ]);
      showToast({
        title: `Generated ${payload.insights.length} v2 insight(s)`,
        variant: "success"
      });
    },
    onError: (error) => {
      showToast({
        title: "V2 generation failed",
        description: getApiErrorMessage(error),
        variant: "error"
      });
    }
  });

  const decideActionMutation = useMutation({
    mutationFn: ({ actionId, decision }: { actionId: string; decision: "approve" | "reject" }) =>
      aiService.decideAction(actionId, { decision }),
    onSuccess: async (action) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["ai", "insights", "v2"] }),
        queryClient.invalidateQueries({ queryKey: ["ai", "actions"] })
      ]);
      showToast({
        title: `Action ${action.status}`,
        variant: "success"
      });
    },
    onError: (error) => {
      showToast({
        title: "Action decision failed",
        description: getApiErrorMessage(error),
        variant: "error"
      });
    }
  });

  const proposedActions = (actionsQuery.data?.items ?? []).filter((item) => item.status === "proposed");

  return (
    <div className="space-y-6">
      <Card className="animate-fade-up bg-[linear-gradient(135deg,#fff_0,#ecfff3_60%,#eef4ff_100%)]">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <p className="inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-surface-600">
              <Bot className="h-4 w-4" /> AI Command Center
            </p>
            <h3 className="mt-1 font-heading text-xl font-bold text-surface-800">
              Ask questions and generate business insights
            </h3>
          </div>
          <Button type="button" variant="secondary" onClick={() => dailyMutation.mutate()} loading={dailyMutation.isPending}>
            <Sparkles className="h-4 w-4" />
            Generate Daily Insight
          </Button>
        </div>

        <form
          className="mt-4 space-y-3"
          onSubmit={form.handleSubmit((values) => askMutation.mutate(values))}
        >
          <Textarea
            label="Business Question"
            placeholder="What is my profit trend and one action I should take this week?"
            rows={4}
            {...form.register("question")}
            error={form.formState.errors.question?.message}
          />
          <Button type="submit" loading={askMutation.isPending}>
            Ask AI
          </Button>
        </form>
      </Card>

      <Card className="animate-fade-up [animation-delay:70ms]">
        <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <div className="grid gap-3 sm:grid-cols-2">
            <Select
              label="Feature Window (Days)"
              value={String(windowDays)}
              onChange={(event) => setWindowDays(Number(event.target.value))}
            >
              <option value="14">14</option>
              <option value="30">30</option>
              <option value="60">60</option>
              <option value="90">90</option>
            </Select>
            <Input
              label="Latest Snapshot End Date"
              value={featureStoreQuery.data?.window_end_date ?? "Not generated"}
              readOnly
            />
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              variant="ghost"
              onClick={() => refreshFeatureStoreMutation.mutate()}
              loading={refreshFeatureStoreMutation.isPending}
            >
              <DatabaseZap className="h-4 w-4" />
              Refresh Feature Store
            </Button>
            <Button
              type="button"
              variant="secondary"
              onClick={() => generateInsightsV2Mutation.mutate()}
              loading={generateInsightsV2Mutation.isPending}
            >
              <Sparkles className="h-4 w-4" />
              Generate V2 Insights
            </Button>
          </div>
        </div>

        {featureStoreQuery.data ? (
          <div className="mt-4 grid gap-3 md:grid-cols-3">
            <div className="rounded-xl border border-surface-100 bg-surface-50 p-3 text-sm text-surface-700">
              <p className="text-xs uppercase tracking-wide text-surface-500">Orders</p>
              <p className="mt-1 font-semibold">{formatNumber(featureStoreQuery.data.orders_count)}</p>
              <p className="text-xs text-surface-500">Paid: {formatNumber(featureStoreQuery.data.paid_orders_count)}</p>
            </div>
            <div className="rounded-xl border border-surface-100 bg-surface-50 p-3 text-sm text-surface-700">
              <p className="text-xs uppercase tracking-wide text-surface-500">Revenue</p>
              <p className="mt-1 font-semibold">{formatCurrency(featureStoreQuery.data.net_revenue)}</p>
              <p className="text-xs text-surface-500">
                Refund Rate: {(featureStoreQuery.data.refund_rate * 100).toFixed(1)}%
              </p>
            </div>
            <div className="rounded-xl border border-surface-100 bg-surface-50 p-3 text-sm text-surface-700">
              <p className="text-xs uppercase tracking-wide text-surface-500">Operational Risk</p>
              <p className="mt-1 font-semibold">
                Stockout: {formatNumber(featureStoreQuery.data.stockout_events_count)}
              </p>
              <p className="text-xs text-surface-500">
                Campaign Failures: {formatNumber(featureStoreQuery.data.campaigns_failed_count)}
              </p>
            </div>
          </div>
        ) : (
          <div className="mt-4 rounded-xl border border-dashed border-surface-200 p-3 text-sm text-surface-500">
            Feature snapshot not found yet. Refresh the feature store to populate event-aware context.
          </div>
        )}
      </Card>

      <Card className="animate-fade-up [animation-delay:90ms]">
        <h3 className="font-heading text-lg font-bold text-surface-800">Insight Log</h3>
        {responses.length === 0 ? (
          <div className="mt-4">
            <EmptyState
              title="No insights yet"
              description="Ask the AI or generate a daily insight to populate this section."
            />
          </div>
        ) : (
          <div className="mt-4 space-y-3">
            {responses.map((entry) => (
              <article key={entry.id} className="rounded-xl border border-surface-100 bg-surface-50 p-4">
                <div className="mb-2 flex flex-wrap items-center gap-2 text-xs">
                  <span className="rounded-full bg-surface-100 px-2 py-1 font-semibold text-surface-700">
                    {entry.insight_type}
                  </span>
                  <span className="rounded-full bg-accent-100 px-2 py-1 font-semibold text-accent-700">
                    {entry.provider}
                  </span>
                  <span className="rounded-full bg-surface-200 px-2 py-1 font-semibold text-surface-700">
                    {entry.model}
                  </span>
                </div>
                <p className="whitespace-pre-wrap text-sm text-surface-700">{entry.response}</p>
                <div className="mt-3 flex flex-wrap gap-3 text-xs text-surface-500">
                  <span>
                    Tokens:{" "}
                    {entry.token_usage?.total_tokens
                      ? formatNumber(entry.token_usage.total_tokens)
                      : "-"}
                  </span>
                  <span>
                    Cost:{" "}
                    {entry.estimated_cost_usd !== null && entry.estimated_cost_usd !== undefined
                      ? formatCurrency(entry.estimated_cost_usd)
                      : "-"}
                  </span>
                  <span>ID: {entry.id}</span>
                </div>
              </article>
            ))}
          </div>
        )}
      </Card>

      <div className="grid gap-6 xl:grid-cols-2">
        <Card className="animate-fade-up [animation-delay:120ms]">
          <h3 className="font-heading text-lg font-bold text-surface-800">V2 Insight Taxonomy</h3>
          {insightsV2Query.data?.items.length ? (
            <div className="mt-4 space-y-3">
              {insightsV2Query.data.items.map((item) => (
                <article key={item.id} className="rounded-xl border border-surface-100 bg-surface-50 p-3">
                  <div className="flex flex-wrap items-center gap-2 text-xs">
                    <span className="rounded-full bg-surface-100 px-2 py-1 font-semibold text-surface-700">
                      {item.insight_type}
                    </span>
                    <span className="rounded-full bg-surface-200 px-2 py-1 font-semibold text-surface-700">
                      {item.severity}
                    </span>
                    <span className="rounded-full bg-accent-100 px-2 py-1 font-semibold text-accent-700">
                      Confidence {(item.confidence_score * 100).toFixed(0)}%
                    </span>
                  </div>
                  <p className="mt-2 text-sm font-semibold text-surface-800">{item.title}</p>
                  <p className="mt-1 text-sm text-surface-600">{item.summary}</p>
                </article>
              ))}
            </div>
          ) : (
            <div className="mt-4">
              <EmptyState
                title="No v2 insights yet"
                description="Generate v2 insights to produce anomaly, urgency, and opportunity items."
              />
            </div>
          )}
        </Card>

        <Card className="animate-fade-up [animation-delay:150ms]">
          <h3 className="font-heading text-lg font-bold text-surface-800">Prescriptive Actions</h3>
          {proposedActions.length ? (
            <div className="mt-4 space-y-3">
              {proposedActions.map((action) => (
                <article key={action.id} className="rounded-xl border border-surface-100 bg-surface-50 p-3">
                  <p className="text-sm font-semibold text-surface-800">{action.title}</p>
                  <p className="mt-1 text-sm text-surface-600">{action.description}</p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <Button
                      type="button"
                      size="sm"
                      onClick={() => decideActionMutation.mutate({ actionId: action.id, decision: "approve" })}
                      loading={decideActionMutation.isPending}
                    >
                      <CheckCheck className="h-4 w-4" />
                      Approve
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      onClick={() => decideActionMutation.mutate({ actionId: action.id, decision: "reject" })}
                      loading={decideActionMutation.isPending}
                    >
                      <X className="h-4 w-4" />
                      Reject
                    </Button>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <div className="mt-4">
              <EmptyState
                title="No proposed actions"
                description="Generate v2 insights to create reviewable prescriptive actions."
              />
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
