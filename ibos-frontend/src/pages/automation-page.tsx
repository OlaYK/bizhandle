import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { automationService } from "../api/services";
import type {
  AutomationActionType,
  AutomationConditionOperator,
  AutomationRunStatus
} from "../api/types";
import { EmptyState } from "../components/state/empty-state";
import { ErrorState } from "../components/state/error-state";
import { LoadingState } from "../components/state/loading-state";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { Select } from "../components/ui/select";
import { Textarea } from "../components/ui/textarea";
import { useToast } from "../hooks/use-toast";
import { getApiErrorMessage } from "../lib/api-error";
import { formatDateTime } from "../lib/format";

type ConditionValueType = "string" | "number" | "boolean" | "json";

interface ActionDraft {
  id: string;
  type: AutomationActionType;
  provider: string;
  recipientFrom: string;
  messageContent: string;
  customerIdFrom: string;
  tagName: string;
  tagColor: string;
  taskTitle: string;
  taskDescription: string;
  dueInHours: string;
  discountCodePrefix: string;
  discountKind: "percentage" | "fixed";
  discountValue: string;
  maxRedemptions: string;
  discountCustomerIdFrom: string;
  discountExpiresInDays: string;
}

function parseJsonObject(raw: string): Record<string, unknown> {
  const cleaned = raw.trim();
  if (!cleaned) return {};
  const parsed = JSON.parse(cleaned) as unknown;
  if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
    return parsed as Record<string, unknown>;
  }
  throw new Error("Payload must be a JSON object");
}

function nextActionDraft(type: AutomationActionType): ActionDraft {
  return {
    id: crypto.randomUUID(),
    type,
    provider: "whatsapp_stub",
    recipientFrom: "payload.phone",
    messageContent:
      type === "send_message" ? "Hello {{payload.customer_name}}, this is your workflow reminder." : "",
    customerIdFrom: "payload.customer_id",
    tagName: "Automated Tag",
    tagColor: "#16a34a",
    taskTitle: "Follow up {{payload.customer_id}}",
    taskDescription: "Generated from automation rule execution.",
    dueInHours: "8",
    discountCodePrefix: "AUTO",
    discountKind: "percentage",
    discountValue: "10",
    maxRedemptions: "1",
    discountCustomerIdFrom: "payload.customer_id",
    discountExpiresInDays: "3"
  };
}

function parseConditionValue(raw: string, valueType: ConditionValueType): unknown {
  const cleaned = raw.trim();
  if (!cleaned) return null;
  if (valueType === "number") {
    return Number(cleaned);
  }
  if (valueType === "boolean") {
    return cleaned.toLowerCase() === "true";
  }
  if (valueType === "json") {
    return JSON.parse(cleaned) as unknown;
  }
  return cleaned;
}

function actionConfigFromDraft(draft: ActionDraft): Record<string, unknown> {
  if (draft.type === "send_message") {
    return {
      provider: draft.provider.trim() || "whatsapp_stub",
      recipient_from: draft.recipientFrom.trim() || "payload.phone",
      content: draft.messageContent.trim()
    };
  }
  if (draft.type === "tag_customer") {
    return {
      customer_id_from: draft.customerIdFrom.trim() || "payload.customer_id",
      tag_name: draft.tagName.trim() || "Automated Tag",
      tag_color: draft.tagColor.trim() || "#16a34a"
    };
  }
  if (draft.type === "create_task") {
    const dueHours = Number(draft.dueInHours || 0);
    return {
      title: draft.taskTitle.trim(),
      description: draft.taskDescription.trim() || undefined,
      due_in_hours: Number.isFinite(dueHours) ? dueHours : 0
    };
  }
  const discountValue = Number(draft.discountValue || 0);
  const maxRedemptions = Number(draft.maxRedemptions || 0);
  const expiresInDays = Number(draft.discountExpiresInDays || 0);
  return {
    code_prefix: draft.discountCodePrefix.trim() || "AUTO",
    kind: draft.discountKind,
    value: Number.isFinite(discountValue) ? discountValue : 0,
    max_redemptions: Number.isFinite(maxRedemptions) && maxRedemptions > 0 ? maxRedemptions : undefined,
    target_customer_id_from: draft.discountCustomerIdFrom.trim() || "payload.customer_id",
    expires_in_days: Number.isFinite(expiresInDays) && expiresInDays > 0 ? expiresInDays : undefined
  };
}

export function AutomationPage() {
  const queryClient = useQueryClient();
  const { showToast } = useToast();

  const [ruleName, setRuleName] = useState("");
  const [ruleDescription, setRuleDescription] = useState("");
  const [triggerEventType, setTriggerEventType] = useState("invoice.overdue");
  const [runLimitPerHour, setRunLimitPerHour] = useState("120");
  const [reentryCooldown, setReentryCooldown] = useState("300");
  const [rollbackOnFailure, setRollbackOnFailure] = useState(true);

  const [conditionField, setConditionField] = useState("payload.amount_due");
  const [conditionOperator, setConditionOperator] = useState<AutomationConditionOperator>("gte");
  const [conditionValueType, setConditionValueType] = useState<ConditionValueType>("number");
  const [conditionValue, setConditionValue] = useState("50");
  const [conditionEnabled, setConditionEnabled] = useState(true);

  const [actions, setActions] = useState<ActionDraft[]>([nextActionDraft("send_message")]);

  const [selectedRuleId, setSelectedRuleId] = useState("");
  const [runStatusFilter, setRunStatusFilter] = useState<"" | AutomationRunStatus>("");
  const [runRuleFilter, setRunRuleFilter] = useState("");

  const [testEventType, setTestEventType] = useState("invoice.overdue");
  const [testPayloadJson, setTestPayloadJson] = useState(
    JSON.stringify(
      {
        invoice_id: "INV-1001",
        amount_due: 120,
        customer_id: "customer-id",
        customer_name: "Automation Customer",
        phone: "+2348011118888"
      },
      null,
      2
    )
  );
  const [testResultSummary, setTestResultSummary] = useState<string | null>(null);

  const templatesQuery = useQuery({
    queryKey: ["automation", "templates"],
    queryFn: automationService.listTemplates
  });

  const rulesQuery = useQuery({
    queryKey: ["automation", "rules"],
    queryFn: () => automationService.listRules({ limit: 100, offset: 0 })
  });

  const runsQuery = useQuery({
    queryKey: ["automation", "runs", runRuleFilter, runStatusFilter],
    queryFn: () =>
      automationService.listRuns({
        rule_id: runRuleFilter || undefined,
        status: runStatusFilter || undefined,
        limit: 25,
        offset: 0
      })
  });

  useEffect(() => {
    if (!selectedRuleId && rulesQuery.data?.items.length) {
      setSelectedRuleId(rulesQuery.data.items[0].id);
      setRunRuleFilter(rulesQuery.data.items[0].id);
      setTestEventType(rulesQuery.data.items[0].trigger_event_type);
    }
  }, [rulesQuery.data, selectedRuleId]);

  const installTemplateMutation = useMutation({
    mutationFn: (templateKey: "abandoned_cart" | "overdue_invoice" | "low_stock") =>
      automationService.installTemplate({ template_key: templateKey, activate: true }),
    onSuccess: (result) => {
      showToast({
        title: "Template installed",
        description: `${result.template.name} is now available as a rule.`,
        variant: "success"
      });
      queryClient.invalidateQueries({ queryKey: ["automation", "rules"] });
      queryClient.invalidateQueries({ queryKey: ["audit-logs"] });
    },
    onError: (error) => {
      showToast({
        title: "Template install failed",
        description: getApiErrorMessage(error),
        variant: "error"
      });
    }
  });

  const createRuleMutation = useMutation({
    mutationFn: () => {
      const parsedRunLimit = Number(runLimitPerHour || 120);
      const parsedCooldown = Number(reentryCooldown || 300);
      return automationService.createRule({
        name: ruleName.trim(),
        description: ruleDescription.trim() || undefined,
        trigger_source: "outbox_event",
        trigger_event_type: triggerEventType.trim(),
        conditions: conditionEnabled
          ? [
              {
                field: conditionField.trim(),
                operator: conditionOperator,
                value: parseConditionValue(conditionValue, conditionValueType)
              }
            ]
          : [],
        actions: actions.map((action) => ({
          type: action.type,
          config_json: actionConfigFromDraft(action)
        })),
        run_limit_per_hour: Number.isFinite(parsedRunLimit) ? parsedRunLimit : 120,
        reentry_cooldown_seconds: Number.isFinite(parsedCooldown) ? parsedCooldown : 300,
        rollback_on_failure: rollbackOnFailure
      });
    },
    onSuccess: (result) => {
      showToast({
        title: "Rule created",
        description: `${result.name} is active and ready to run.`,
        variant: "success"
      });
      setRuleName("");
      setRuleDescription("");
      setSelectedRuleId(result.id);
      setRunRuleFilter(result.id);
      queryClient.invalidateQueries({ queryKey: ["automation", "rules"] });
      queryClient.invalidateQueries({ queryKey: ["audit-logs"] });
    },
    onError: (error) => {
      showToast({
        title: "Rule creation failed",
        description: getApiErrorMessage(error),
        variant: "error"
      });
    }
  });

  const toggleRuleMutation = useMutation({
    mutationFn: (params: { ruleId: string; status: "active" | "inactive" }) =>
      automationService.updateRule(params.ruleId, { status: params.status }),
    onSuccess: () => {
      showToast({ title: "Rule updated", variant: "success" });
      queryClient.invalidateQueries({ queryKey: ["automation", "rules"] });
      queryClient.invalidateQueries({ queryKey: ["audit-logs"] });
    },
    onError: (error) => {
      showToast({
        title: "Rule update failed",
        description: getApiErrorMessage(error),
        variant: "error"
      });
    }
  });

  const testRuleMutation = useMutation({
    mutationFn: () => {
      if (!selectedRuleId) {
        throw new Error("Select a rule to test");
      }
      return automationService.testRule(selectedRuleId, {
        event_type: testEventType.trim() || undefined,
        target_app_key: "automation",
        payload_json: parseJsonObject(testPayloadJson)
      });
    },
    onSuccess: (result) => {
      setTestResultSummary(
        `Dry run status: ${result.status}. Steps: ${result.steps_total}, failures: ${result.steps_failed}.`
      );
      queryClient.invalidateQueries({ queryKey: ["automation", "runs"] });
    },
    onError: (error) => {
      showToast({
        title: "Dry run failed",
        description: getApiErrorMessage(error),
        variant: "error"
      });
    }
  });

  const runOutboxMutation = useMutation({
    mutationFn: () => automationService.runOutbox(100),
    onSuccess: (result) => {
      showToast({
        title: "Outbox execution complete",
        description: `Runs: ${result.triggered_runs}, success: ${result.successful_runs}, blocked: ${result.blocked_runs}.`,
        variant: "success"
      });
      queryClient.invalidateQueries({ queryKey: ["automation", "runs"] });
      queryClient.invalidateQueries({ queryKey: ["audit-logs"] });
    },
    onError: (error) => {
      showToast({
        title: "Outbox execution failed",
        description: getApiErrorMessage(error),
        variant: "error"
      });
    }
  });

  const selectedRule = useMemo(
    () => rulesQuery.data?.items.find((item) => item.id === selectedRuleId),
    [rulesQuery.data?.items, selectedRuleId]
  );

  if (templatesQuery.isLoading || rulesQuery.isLoading || runsQuery.isLoading) {
    return <LoadingState label="Loading automation workspace..." />;
  }

  if (
    templatesQuery.isError ||
    rulesQuery.isError ||
    runsQuery.isError ||
    !templatesQuery.data ||
    !rulesQuery.data ||
    !runsQuery.data
  ) {
    return (
      <ErrorState
        message="Could not load automation workspace."
        onRetry={() => {
          templatesQuery.refetch();
          rulesQuery.refetch();
          runsQuery.refetch();
        }}
      />
    );
  }

  const canCreateRule =
    ruleName.trim().length >= 2 &&
    triggerEventType.trim().length >= 2 &&
    actions.length > 0 &&
    actions.every((action) => {
      if (action.type === "send_message") return action.messageContent.trim().length > 0;
      if (action.type === "tag_customer") return action.tagName.trim().length > 0;
      if (action.type === "create_task") return action.taskTitle.trim().length > 0;
      return Number(action.discountValue || 0) > 0;
    });

  return (
    <div className="space-y-6">
      <Card className="animate-fade-up bg-[linear-gradient(135deg,#14303f_0%,#1e4d5f_55%,#2d6472_100%)] text-white">
        <h3 className="font-heading text-xl font-black">Automation Workflow Engine</h3>
        <p className="mt-1 text-sm text-white/80">
          Build event-driven rules with guardrails, run dry tests, and inspect step-by-step execution logs.
        </p>
        <div className="mt-4 flex flex-wrap gap-2">
          <Badge variant="info">{rulesQuery.data.pagination.total} rules</Badge>
          <Badge variant="info">{runsQuery.data.pagination.total} run logs</Badge>
        </div>
      </Card>

      <Card>
        <h3 className="font-heading text-lg font-bold text-surface-800">Template Library</h3>
        <div className="mt-4 grid gap-3 md:grid-cols-3">
          {templatesQuery.data.items.map((template) => (
            <article key={template.template_key} className="rounded-xl border border-surface-100 bg-surface-50 p-3">
              <p className="font-semibold text-surface-700">{template.name}</p>
              <p className="mt-1 text-xs text-surface-500">{template.description}</p>
              <p className="mt-2 text-xs text-surface-500">Trigger: {template.trigger_event_type}</p>
              <Button
                type="button"
                size="sm"
                className="mt-3"
                loading={
                  installTemplateMutation.isPending &&
                  installTemplateMutation.variables === template.template_key
                }
                onClick={() => installTemplateMutation.mutate(template.template_key)}
              >
                Install Template
              </Button>
            </article>
          ))}
        </div>
      </Card>

      <Card>
        <h3 className="font-heading text-lg font-bold text-surface-800">No-code Rule Builder</h3>
        <div className="mt-4 grid gap-3 lg:grid-cols-3">
          <Input label="Rule Name" value={ruleName} onChange={(event) => setRuleName(event.target.value)} />
          <Input
            label="Trigger Event Type"
            value={triggerEventType}
            onChange={(event) => setTriggerEventType(event.target.value)}
          />
          <Input
            label="Description"
            value={ruleDescription}
            onChange={(event) => setRuleDescription(event.target.value)}
          />
        </div>

        <div className="mt-4 grid gap-3 lg:grid-cols-4">
          <Select
            label="Condition Enabled"
            value={conditionEnabled ? "yes" : "no"}
            onChange={(event) => setConditionEnabled(event.target.value === "yes")}
          >
            <option value="yes">yes</option>
            <option value="no">no</option>
          </Select>
          <Input
            label="Condition Field"
            value={conditionField}
            onChange={(event) => setConditionField(event.target.value)}
            disabled={!conditionEnabled}
          />
          <Select
            label="Condition Operator"
            value={conditionOperator}
            onChange={(event) => setConditionOperator(event.target.value as AutomationConditionOperator)}
            disabled={!conditionEnabled}
          >
            <option value="eq">eq</option>
            <option value="neq">neq</option>
            <option value="gt">gt</option>
            <option value="gte">gte</option>
            <option value="lt">lt</option>
            <option value="lte">lte</option>
            <option value="contains">contains</option>
            <option value="in">in</option>
            <option value="exists">exists</option>
            <option value="not_exists">not_exists</option>
          </Select>
          <Input
            label="Condition Value"
            value={conditionValue}
            onChange={(event) => setConditionValue(event.target.value)}
            disabled={!conditionEnabled}
          />
        </div>

        <div className="mt-4 grid gap-3 lg:grid-cols-4">
          <Select
            label="Condition Value Type"
            value={conditionValueType}
            onChange={(event) => setConditionValueType(event.target.value as ConditionValueType)}
          >
            <option value="string">string</option>
            <option value="number">number</option>
            <option value="boolean">boolean</option>
            <option value="json">json</option>
          </Select>
          <Input
            label="Run Limit / Hour"
            value={runLimitPerHour}
            onChange={(event) => setRunLimitPerHour(event.target.value)}
          />
          <Input
            label="Re-entry Cooldown (sec)"
            value={reentryCooldown}
            onChange={(event) => setReentryCooldown(event.target.value)}
          />
          <Select
            label="Rollback on Failure"
            value={rollbackOnFailure ? "yes" : "no"}
            onChange={(event) => setRollbackOnFailure(event.target.value === "yes")}
          >
            <option value="yes">yes</option>
            <option value="no">no</option>
          </Select>
        </div>

        <div className="mt-5 space-y-3">
          <div className="flex items-center justify-between">
            <h4 className="font-semibold text-surface-700">Actions</h4>
            <Button
              type="button"
              variant="ghost"
              onClick={() => setActions((prev) => [...prev, nextActionDraft("create_task")])}
            >
              Add Action
            </Button>
          </div>
          {actions.map((action, index) => (
            <article key={action.id} className="rounded-xl border border-surface-100 bg-surface-50 p-3">
              <div className="grid gap-3 lg:grid-cols-4">
                <Select
                  label={`Action ${index + 1} Type`}
                  value={action.type}
                  onChange={(event) =>
                    setActions((prev) =>
                      prev.map((item) =>
                        item.id === action.id
                          ? { ...nextActionDraft(event.target.value as AutomationActionType), id: item.id }
                          : item
                      )
                    )
                  }
                >
                  <option value="send_message">send_message</option>
                  <option value="tag_customer">tag_customer</option>
                  <option value="create_task">create_task</option>
                  <option value="apply_discount">apply_discount</option>
                </Select>
                {action.type === "send_message" ? (
                  <>
                    <Input
                      label="Provider"
                      value={action.provider}
                      onChange={(event) =>
                        setActions((prev) =>
                          prev.map((item) =>
                            item.id === action.id ? { ...item, provider: event.target.value } : item
                          )
                        )
                      }
                    />
                    <Input
                      label="Recipient Path"
                      value={action.recipientFrom}
                      onChange={(event) =>
                        setActions((prev) =>
                          prev.map((item) =>
                            item.id === action.id ? { ...item, recipientFrom: event.target.value } : item
                          )
                        )
                      }
                    />
                    <Input
                      label="Message Template"
                      value={action.messageContent}
                      onChange={(event) =>
                        setActions((prev) =>
                          prev.map((item) =>
                            item.id === action.id ? { ...item, messageContent: event.target.value } : item
                          )
                        )
                      }
                    />
                  </>
                ) : null}
                {action.type === "tag_customer" ? (
                  <>
                    <Input
                      label="Customer ID Path"
                      value={action.customerIdFrom}
                      onChange={(event) =>
                        setActions((prev) =>
                          prev.map((item) =>
                            item.id === action.id ? { ...item, customerIdFrom: event.target.value } : item
                          )
                        )
                      }
                    />
                    <Input
                      label="Tag Name"
                      value={action.tagName}
                      onChange={(event) =>
                        setActions((prev) =>
                          prev.map((item) => (item.id === action.id ? { ...item, tagName: event.target.value } : item))
                        )
                      }
                    />
                    <Input
                      label="Tag Color"
                      value={action.tagColor}
                      onChange={(event) =>
                        setActions((prev) =>
                          prev.map((item) => (item.id === action.id ? { ...item, tagColor: event.target.value } : item))
                        )
                      }
                    />
                  </>
                ) : null}
                {action.type === "create_task" ? (
                  <>
                    <Input
                      label="Task Title"
                      value={action.taskTitle}
                      onChange={(event) =>
                        setActions((prev) =>
                          prev.map((item) =>
                            item.id === action.id ? { ...item, taskTitle: event.target.value } : item
                          )
                        )
                      }
                    />
                    <Input
                      label="Task Description"
                      value={action.taskDescription}
                      onChange={(event) =>
                        setActions((prev) =>
                          prev.map((item) =>
                            item.id === action.id ? { ...item, taskDescription: event.target.value } : item
                          )
                        )
                      }
                    />
                    <Input
                      label="Due in Hours"
                      value={action.dueInHours}
                      onChange={(event) =>
                        setActions((prev) =>
                          prev.map((item) =>
                            item.id === action.id ? { ...item, dueInHours: event.target.value } : item
                          )
                        )
                      }
                    />
                  </>
                ) : null}
                {action.type === "apply_discount" ? (
                  <>
                    <Input
                      label="Code Prefix"
                      value={action.discountCodePrefix}
                      onChange={(event) =>
                        setActions((prev) =>
                          prev.map((item) =>
                            item.id === action.id ? { ...item, discountCodePrefix: event.target.value } : item
                          )
                        )
                      }
                    />
                    <Select
                      label="Kind"
                      value={action.discountKind}
                      onChange={(event) =>
                        setActions((prev) =>
                          prev.map((item) =>
                            item.id === action.id
                              ? { ...item, discountKind: event.target.value as "percentage" | "fixed" }
                              : item
                          )
                        )
                      }
                    >
                      <option value="percentage">percentage</option>
                      <option value="fixed">fixed</option>
                    </Select>
                    <Input
                      label="Value"
                      value={action.discountValue}
                      onChange={(event) =>
                        setActions((prev) =>
                          prev.map((item) =>
                            item.id === action.id ? { ...item, discountValue: event.target.value } : item
                          )
                        )
                      }
                    />
                    <Input
                      label="Max Redemptions"
                      value={action.maxRedemptions}
                      onChange={(event) =>
                        setActions((prev) =>
                          prev.map((item) =>
                            item.id === action.id ? { ...item, maxRedemptions: event.target.value } : item
                          )
                        )
                      }
                    />
                  </>
                ) : null}
              </div>
              <div className="mt-3 flex items-center gap-2">
                <Button
                  type="button"
                  variant="danger"
                  size="sm"
                  disabled={actions.length === 1}
                  onClick={() => setActions((prev) => prev.filter((item) => item.id !== action.id))}
                >
                  Remove
                </Button>
              </div>
            </article>
          ))}
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          <Button
            type="button"
            loading={createRuleMutation.isPending}
            disabled={!canCreateRule}
            onClick={() => createRuleMutation.mutate()}
          >
            Create Rule
          </Button>
          <Button
            type="button"
            variant="secondary"
            loading={runOutboxMutation.isPending}
            onClick={() => runOutboxMutation.mutate()}
          >
            Run Outbox Now
          </Button>
        </div>
      </Card>

      <div className="grid gap-6 xl:grid-cols-2">
        <Card>
          <h3 className="font-heading text-lg font-bold text-surface-800">Rules</h3>
          {!rulesQuery.data.items.length ? (
            <div className="mt-3">
              <EmptyState title="No rules yet" description="Create your first workflow rule." />
            </div>
          ) : (
            <div className="mt-3 space-y-2">
              {rulesQuery.data.items.map((rule) => (
                <article key={rule.id} className="rounded-xl border border-surface-100 bg-surface-50 p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <p className="font-semibold text-surface-700">{rule.name}</p>
                      <p className="text-xs text-surface-500">
                        Trigger: {rule.trigger_event_type} | version {rule.version}
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge variant={rule.status === "active" ? "positive" : "neutral"}>{rule.status}</Badge>
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        onClick={() => {
                          setSelectedRuleId(rule.id);
                          setRunRuleFilter(rule.id);
                          setTestEventType(rule.trigger_event_type);
                        }}
                      >
                        Select
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="secondary"
                        loading={
                          toggleRuleMutation.isPending &&
                          toggleRuleMutation.variables?.ruleId === rule.id
                        }
                        onClick={() =>
                          toggleRuleMutation.mutate({
                            ruleId: rule.id,
                            status: rule.status === "active" ? "inactive" : "active"
                          })
                        }
                      >
                        {rule.status === "active" ? "Disable" : "Enable"}
                      </Button>
                    </div>
                  </div>
                  <p className="mt-1 text-xs text-surface-500">
                    Actions: {rule.actions.length} | Updated: {formatDateTime(rule.updated_at)}
                  </p>
                </article>
              ))}
            </div>
          )}
        </Card>
        <Card>
          <h3 className="font-heading text-lg font-bold text-surface-800">Dry Run Tester</h3>
          <div className="mt-3 grid gap-3">
            <Select value={selectedRuleId} onChange={(event) => setSelectedRuleId(event.target.value)} label="Rule">
              <option value="">Select rule</option>
              {rulesQuery.data.items.map((rule) => (
                <option key={rule.id} value={rule.id}>
                  {rule.name}
                </option>
              ))}
            </Select>
            <Input
              label="Event Type"
              value={testEventType}
              onChange={(event) => setTestEventType(event.target.value)}
            />
            <Textarea
              label="Payload JSON"
              rows={8}
              value={testPayloadJson}
              onChange={(event) => setTestPayloadJson(event.target.value)}
            />
            <Button
              type="button"
              loading={testRuleMutation.isPending}
              disabled={!selectedRuleId}
              onClick={() => testRuleMutation.mutate()}
            >
              Run Dry Test
            </Button>
            {testResultSummary ? (
              <p className="text-sm font-semibold text-surface-700">{testResultSummary}</p>
            ) : null}
            {selectedRule ? (
              <p className="text-xs text-surface-500">
                Selected trigger pattern: <strong>{selectedRule.trigger_event_type}</strong>
              </p>
            ) : null}
          </div>
        </Card>
      </div>

      <Card>
        <div className="flex flex-wrap items-end gap-3">
          <Select
            label="Rule Filter"
            value={runRuleFilter}
            onChange={(event) => setRunRuleFilter(event.target.value)}
            className="max-w-xs"
          >
            <option value="">All rules</option>
            {rulesQuery.data.items.map((rule) => (
              <option key={rule.id} value={rule.id}>
                {rule.name}
              </option>
            ))}
          </Select>
          <Select
            label="Status Filter"
            value={runStatusFilter}
            onChange={(event) => setRunStatusFilter(event.target.value as "" | AutomationRunStatus)}
            className="max-w-xs"
          >
            <option value="">All statuses</option>
            <option value="success">success</option>
            <option value="failed">failed</option>
            <option value="blocked">blocked</option>
            <option value="skipped">skipped</option>
            <option value="dry_run">dry_run</option>
          </Select>
          <Button type="button" variant="secondary" onClick={() => runsQuery.refetch()}>
            Refresh Logs
          </Button>
        </div>

        {!runsQuery.data.items.length ? (
          <div className="mt-4">
            <EmptyState title="No workflow runs yet" description="Execute outbox run or dry test to populate logs." />
          </div>
        ) : (
          <div className="mt-4 space-y-3">
            {runsQuery.data.items.map((run) => (
              <article key={run.id} className="rounded-xl border border-surface-100 bg-surface-50 p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <p className="font-semibold text-surface-700">{run.trigger_event_type}</p>
                    <p className="text-xs text-surface-500">
                      Run ID: {run.id} | Rule: {run.rule_id} | Created: {formatDateTime(run.created_at)}
                    </p>
                  </div>
                  <Badge
                    variant={
                      run.status === "success"
                        ? "positive"
                        : run.status === "failed" || run.status === "blocked"
                          ? "negative"
                          : "info"
                    }
                  >
                    {run.status}
                  </Badge>
                </div>
                {run.blocked_reason ? (
                  <p className="mt-1 text-xs text-amber-700">Blocked: {run.blocked_reason}</p>
                ) : null}
                {run.error_message ? (
                  <p className="mt-1 text-xs text-red-600">Error: {run.error_message}</p>
                ) : null}
                <div className="mt-2 grid gap-2">
                  {run.steps.map((step) => (
                    <div key={`${run.id}-${step.step_index}`} className="rounded-lg border border-surface-200 bg-white p-2">
                      <div className="flex items-center justify-between gap-2">
                        <p className="text-sm font-semibold text-surface-700">
                          {step.step_index}. {step.action_type}
                        </p>
                        <Badge variant={step.status === "failed" ? "negative" : "info"}>{step.status}</Badge>
                      </div>
                      {step.error_message ? (
                        <p className="mt-1 text-xs text-red-600">{step.error_message}</p>
                      ) : null}
                    </div>
                  ))}
                </div>
              </article>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
