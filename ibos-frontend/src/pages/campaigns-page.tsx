import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { campaignService } from "../api/services";
import type {
  CampaignChannel,
  CampaignOut,
  CampaignRecipientStatus,
  CampaignStatus,
  CampaignTemplateStatus
} from "../api/types";
import { EmptyState } from "../components/state/empty-state";
import { ErrorState } from "../components/state/error-state";
import { LoadingState } from "../components/state/loading-state";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { PaginationControls } from "../components/ui/pagination-controls";
import { Select } from "../components/ui/select";
import { Textarea } from "../components/ui/textarea";
import { useToast } from "../hooks/use-toast";
import { getApiErrorMessage } from "../lib/api-error";
import { formatDateTime } from "../lib/format";

type YesNoAny = "any" | "yes" | "no";

const CHANNEL_OPTIONS: CampaignChannel[] = ["whatsapp", "sms", "email"];

export function CampaignsPage() {
  const queryClient = useQueryClient();
  const { showToast } = useToast();

  const [segmentName, setSegmentName] = useState("");
  const [segmentDescription, setSegmentDescription] = useState("");
  const [segmentHasPhone, setSegmentHasPhone] = useState<YesNoAny>("any");
  const [previewBySegment, setPreviewBySegment] = useState<Record<string, number>>({});

  const [templateName, setTemplateName] = useState("");
  const [templateChannel, setTemplateChannel] = useState<CampaignChannel>("whatsapp");
  const [templateStatus, setTemplateStatus] = useState<CampaignTemplateStatus>("draft");
  const [templateContent, setTemplateContent] = useState("");

  const [campaignName, setCampaignName] = useState("");
  const [campaignSegmentId, setCampaignSegmentId] = useState("");
  const [campaignTemplateId, setCampaignTemplateId] = useState("");
  const [campaignChannel, setCampaignChannel] = useState<CampaignChannel>("whatsapp");
  const [campaignSendNow, setCampaignSendNow] = useState(true);

  const [campaignStatusFilter, setCampaignStatusFilter] = useState<"" | CampaignStatus>("");
  const [campaignPage, setCampaignPage] = useState(1);
  const [campaignPageSize, setCampaignPageSize] = useState(20);

  const [selectedCampaignId, setSelectedCampaignId] = useState("");
  const [recipientStatusFilter, setRecipientStatusFilter] = useState<"" | CampaignRecipientStatus>("");

  const [consentCustomerId, setConsentCustomerId] = useState("");
  const [consentChannel, setConsentChannel] = useState<CampaignChannel>("whatsapp");
  const [consentStatus, setConsentStatus] = useState<"subscribed" | "unsubscribed">("unsubscribed");
  const [consentSource, setConsentSource] = useState("manual");
  const [consentPage, setConsentPage] = useState(1);
  const [consentPageSize, setConsentPageSize] = useState(10);

  const [triggerName, setTriggerName] = useState("");
  const [triggerSegmentId, setTriggerSegmentId] = useState("");
  const [triggerTemplateId, setTriggerTemplateId] = useState("");
  const [triggerChannel, setTriggerChannel] = useState<CampaignChannel>("whatsapp");
  const [triggerAutoDispatch, setTriggerAutoDispatch] = useState(true);

  const campaignOffset = (campaignPage - 1) * campaignPageSize;
  const consentOffset = (consentPage - 1) * consentPageSize;

  useEffect(() => {
    setCampaignPage(1);
  }, [campaignStatusFilter]);

  const segmentsQuery = useQuery({
    queryKey: ["campaigns", "segments"],
    queryFn: () => campaignService.listSegments({ limit: 100, offset: 0 })
  });

  const templatesQuery = useQuery({
    queryKey: ["campaigns", "templates"],
    queryFn: () => campaignService.listTemplates({ limit: 100, offset: 0 })
  });

  const campaignsQuery = useQuery({
    queryKey: ["campaigns", "list", campaignStatusFilter, campaignPage, campaignPageSize],
    queryFn: () =>
      campaignService.listCampaigns({
        status: campaignStatusFilter || undefined,
        limit: campaignPageSize,
        offset: campaignOffset
      })
  });

  const metricsQuery = useQuery({
    queryKey: ["campaigns", "metrics"],
    queryFn: () => campaignService.metrics()
  });

  const consentsQuery = useQuery({
    queryKey: ["campaigns", "consents", consentPage, consentPageSize],
    queryFn: () =>
      campaignService.listConsents({
        limit: consentPageSize,
        offset: consentOffset
      })
  });

  const triggersQuery = useQuery({
    queryKey: ["campaigns", "triggers"],
    queryFn: () => campaignService.listRetentionTriggers({ limit: 50, offset: 0 })
  });

  const recipientsQuery = useQuery({
    queryKey: ["campaigns", "recipients", selectedCampaignId, recipientStatusFilter],
    queryFn: () =>
      campaignService.listRecipients(selectedCampaignId, {
        status: recipientStatusFilter || undefined,
        limit: 50,
        offset: 0
      }),
    enabled: Boolean(selectedCampaignId)
  });

  const selectedTemplate = useMemo(
    () => templatesQuery.data?.items.find((template) => template.id === campaignTemplateId),
    [campaignTemplateId, templatesQuery.data?.items]
  );

  useEffect(() => {
    if (selectedTemplate) {
      setCampaignChannel(selectedTemplate.channel);
    }
  }, [selectedTemplate]);

  const createSegmentMutation = useMutation({
    mutationFn: () =>
      campaignService.createSegment({
        name: segmentName.trim(),
        description: segmentDescription.trim() || undefined,
        filters:
          segmentHasPhone === "any"
            ? {}
            : {
                has_phone: segmentHasPhone === "yes"
              }
      }),
    onSuccess: () => {
      showToast({ title: "Segment created", variant: "success" });
      setSegmentName("");
      setSegmentDescription("");
      setSegmentHasPhone("any");
      queryClient.invalidateQueries({ queryKey: ["campaigns", "segments"] });
      queryClient.invalidateQueries({ queryKey: ["audit-logs"] });
    },
    onError: (error) => {
      showToast({
        title: "Could not create segment",
        description: getApiErrorMessage(error),
        variant: "error"
      });
    }
  });

  const previewSegmentMutation = useMutation({
    mutationFn: (segmentId: string) => campaignService.previewSegment(segmentId),
    onSuccess: (result) => {
      setPreviewBySegment((state) => ({ ...state, [result.segment_id]: result.total_customers }));
    },
    onError: (error) => {
      showToast({
        title: "Could not preview segment",
        description: getApiErrorMessage(error),
        variant: "error"
      });
    }
  });

  const createTemplateMutation = useMutation({
    mutationFn: () =>
      campaignService.createTemplate({
        name: templateName.trim(),
        channel: templateChannel,
        content: templateContent.trim(),
        status: templateStatus
      }),
    onSuccess: () => {
      showToast({ title: "Template created", variant: "success" });
      setTemplateName("");
      setTemplateContent("");
      setTemplateStatus("draft");
      queryClient.invalidateQueries({ queryKey: ["campaigns", "templates"] });
      queryClient.invalidateQueries({ queryKey: ["audit-logs"] });
    },
    onError: (error) => {
      showToast({
        title: "Could not create template",
        description: getApiErrorMessage(error),
        variant: "error"
      });
    }
  });

  const approveTemplateMutation = useMutation({
    mutationFn: (templateId: string) =>
      campaignService.updateTemplate(templateId, {
        status: "approved"
      }),
    onSuccess: () => {
      showToast({ title: "Template approved", variant: "success" });
      queryClient.invalidateQueries({ queryKey: ["campaigns", "templates"] });
      queryClient.invalidateQueries({ queryKey: ["audit-logs"] });
    },
    onError: (error) => {
      showToast({
        title: "Template update failed",
        description: getApiErrorMessage(error),
        variant: "error"
      });
    }
  });

  const createCampaignMutation = useMutation({
    mutationFn: () =>
      campaignService.createCampaign({
        name: campaignName.trim(),
        segment_id: campaignSegmentId || undefined,
        template_id: campaignTemplateId || undefined,
        channel: campaignChannel,
        provider: "whatsapp_stub",
        send_now: campaignSendNow
      }),
    onSuccess: (result) => {
      showToast({
        title: "Campaign created",
        description: `${result.total_recipients} recipients prepared.`,
        variant: "success"
      });
      setCampaignName("");
      setSelectedCampaignId(result.id);
      queryClient.invalidateQueries({ queryKey: ["campaigns", "list"] });
      queryClient.invalidateQueries({ queryKey: ["campaigns", "metrics"] });
      queryClient.invalidateQueries({ queryKey: ["campaigns", "recipients"] });
      queryClient.invalidateQueries({ queryKey: ["audit-logs"] });
    },
    onError: (error) => {
      showToast({
        title: "Could not create campaign",
        description: getApiErrorMessage(error),
        variant: "error"
      });
    }
  });

  const dispatchCampaignMutation = useMutation({
    mutationFn: (campaignId: string) => campaignService.dispatchCampaign(campaignId),
    onSuccess: (result) => {
      showToast({
        title: "Dispatch completed",
        description: `Sent ${result.sent}, failed ${result.failed}, skipped ${result.skipped}.`,
        variant: "success"
      });
      queryClient.invalidateQueries({ queryKey: ["campaigns", "list"] });
      queryClient.invalidateQueries({ queryKey: ["campaigns", "metrics"] });
      queryClient.invalidateQueries({ queryKey: ["campaigns", "recipients"] });
      queryClient.invalidateQueries({ queryKey: ["audit-logs"] });
    },
    onError: (error) => {
      showToast({
        title: "Dispatch failed",
        description: getApiErrorMessage(error),
        variant: "error"
      });
    }
  });

  const upsertConsentMutation = useMutation({
    mutationFn: () =>
      campaignService.upsertConsent({
        customer_id: consentCustomerId.trim(),
        channel: consentChannel,
        status: consentStatus,
        source: consentSource.trim() || undefined
      }),
    onSuccess: () => {
      showToast({ title: "Consent updated", variant: "success" });
      setConsentCustomerId("");
      queryClient.invalidateQueries({ queryKey: ["campaigns", "consents"] });
      queryClient.invalidateQueries({ queryKey: ["audit-logs"] });
    },
    onError: (error) => {
      showToast({
        title: "Consent update failed",
        description: getApiErrorMessage(error),
        variant: "error"
      });
    }
  });

  const createTriggerMutation = useMutation({
    mutationFn: () =>
      campaignService.createRetentionTrigger({
        name: triggerName.trim(),
        trigger_type: "repeat_purchase_nudge",
        status: "active",
        segment_id: triggerSegmentId || undefined,
        template_id: triggerTemplateId || undefined,
        channel: triggerChannel,
        provider: "whatsapp_stub",
        config_json: { source: "campaigns_page" }
      }),
    onSuccess: () => {
      showToast({ title: "Retention trigger created", variant: "success" });
      setTriggerName("");
      queryClient.invalidateQueries({ queryKey: ["campaigns", "triggers"] });
      queryClient.invalidateQueries({ queryKey: ["audit-logs"] });
    },
    onError: (error) => {
      showToast({
        title: "Could not create retention trigger",
        description: getApiErrorMessage(error),
        variant: "error"
      });
    }
  });

  const runTriggerMutation = useMutation({
    mutationFn: (triggerId: string) =>
      campaignService.runRetentionTrigger(triggerId, {
        auto_dispatch: triggerAutoDispatch
      }),
    onSuccess: (result) => {
      showToast({
        title: "Retention trigger executed",
        description: `Processed ${result.processed_count} recipients.`,
        variant: "success"
      });
      queryClient.invalidateQueries({ queryKey: ["campaigns", "list"] });
      queryClient.invalidateQueries({ queryKey: ["campaigns", "metrics"] });
      queryClient.invalidateQueries({ queryKey: ["campaigns", "triggers"] });
      queryClient.invalidateQueries({ queryKey: ["audit-logs"] });
    },
    onError: (error) => {
      showToast({
        title: "Retention run failed",
        description: getApiErrorMessage(error),
        variant: "error"
      });
    }
  });

  const selectedCampaign = useMemo(
    () => campaignsQuery.data?.items.find((item) => item.id === selectedCampaignId),
    [campaignsQuery.data?.items, selectedCampaignId]
  );

  if (
    segmentsQuery.isLoading ||
    templatesQuery.isLoading ||
    campaignsQuery.isLoading ||
    metricsQuery.isLoading ||
    consentsQuery.isLoading ||
    triggersQuery.isLoading
  ) {
    return <LoadingState label="Loading campaign operations..." />;
  }

  if (
    segmentsQuery.isError ||
    templatesQuery.isError ||
    campaignsQuery.isError ||
    metricsQuery.isError ||
    consentsQuery.isError ||
    triggersQuery.isError ||
    !segmentsQuery.data ||
    !templatesQuery.data ||
    !campaignsQuery.data ||
    !metricsQuery.data ||
    !consentsQuery.data ||
    !triggersQuery.data
  ) {
    return (
      <ErrorState
        message="Could not load campaigns workspace."
        onRetry={() => {
          segmentsQuery.refetch();
          templatesQuery.refetch();
          campaignsQuery.refetch();
          metricsQuery.refetch();
          consentsQuery.refetch();
          triggersQuery.refetch();
        }}
      />
    );
  }

  const segments = segmentsQuery.data.items;
  const templates = templatesQuery.data.items;
  const campaigns = campaignsQuery.data.items;
  const metrics = metricsQuery.data;
  const consents = consentsQuery.data.items;
  const triggers = triggersQuery.data.items;

  const canCreateCampaign =
    campaignName.trim().length > 1 && (campaignTemplateId.trim().length > 0 || campaignSegmentId.trim().length > 0);

  return (
    <div className="space-y-6">
      <Card className="animate-fade-up bg-[linear-gradient(135deg,#0f2742_0%,#244f72_55%,#32728a_100%)] text-white">
        <h3 className="font-heading text-xl font-black">Campaigns and Retention</h3>
        <p className="mt-1 text-sm text-white/80">
          Build reusable segments, enforce opt-out controls, and execute campaigns with measurable outcomes.
        </p>
        <div className="mt-4 flex flex-wrap gap-2">
          <Badge variant="info">{metrics.campaigns_total} campaigns</Badge>
          <Badge variant="info">{metrics.recipients_total} recipients</Badge>
          <Badge variant="positive">{metrics.sent_count} sent</Badge>
          <Badge variant="negative">{metrics.failed_count} failed</Badge>
          <Badge variant="neutral">{metrics.suppressed_count} suppressed</Badge>
          <Badge variant="info">{metrics.response_rate}% response rate</Badge>
        </div>
      </Card>

      <div className="grid gap-6 xl:grid-cols-2">
        <Card>
          <h3 className="font-heading text-lg font-bold text-surface-800">Dynamic Segments</h3>
          <div className="mt-4 grid gap-3">
            <Input
              label="Segment Name"
              placeholder="VIP Phone Contacts"
              value={segmentName}
              onChange={(event) => setSegmentName(event.target.value)}
            />
            <Input
              label="Description"
              placeholder="Used for WhatsApp campaigns"
              value={segmentDescription}
              onChange={(event) => setSegmentDescription(event.target.value)}
            />
            <Select
              label="Filter: Has Phone"
              value={segmentHasPhone}
              onChange={(event) => setSegmentHasPhone(event.target.value as YesNoAny)}
            >
              <option value="any">Any</option>
              <option value="yes">Yes</option>
              <option value="no">No</option>
            </Select>
            <Button
              type="button"
              loading={createSegmentMutation.isPending}
              disabled={segmentName.trim().length < 2}
              onClick={() => createSegmentMutation.mutate()}
            >
              Save Segment
            </Button>
          </div>

          <div className="mt-4 space-y-2">
            {!segments.length ? (
              <EmptyState
                title="No segments yet"
                description="Create the first saved segment to start campaign targeting."
              />
            ) : (
              segments.map((segment) => (
                <article key={segment.id} className="rounded-xl border border-surface-100 bg-surface-50 p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="font-semibold text-surface-700">{segment.name}</p>
                    <Badge variant={segment.is_active ? "positive" : "neutral"}>
                      {segment.is_active ? "active" : "inactive"}
                    </Badge>
                  </div>
                  <p className="mt-1 text-xs text-surface-500">{segment.description || "No description"}</p>
                  <div className="mt-2 flex items-center justify-between gap-2">
                    <p className="text-xs text-surface-500">Updated: {formatDateTime(segment.updated_at)}</p>
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      loading={
                        previewSegmentMutation.isPending &&
                        previewSegmentMutation.variables === segment.id
                      }
                      onClick={() => previewSegmentMutation.mutate(segment.id)}
                    >
                      Preview
                    </Button>
                  </div>
                  {previewBySegment[segment.id] !== undefined ? (
                    <p className="mt-1 text-xs font-semibold text-surface-700">
                      Preview audience: {previewBySegment[segment.id]}
                    </p>
                  ) : null}
                </article>
              ))
            )}
          </div>
        </Card>

        <Card>
          <h3 className="font-heading text-lg font-bold text-surface-800">Template Library</h3>
          <div className="mt-4 grid gap-3">
            <Input
              label="Template Name"
              placeholder="Lapsed Buyer Reminder"
              value={templateName}
              onChange={(event) => setTemplateName(event.target.value)}
            />
            <div className="grid gap-3 sm:grid-cols-2">
              <Select
                label="Channel"
                value={templateChannel}
                onChange={(event) => setTemplateChannel(event.target.value as CampaignChannel)}
              >
                {CHANNEL_OPTIONS.map((channel) => (
                  <option key={channel} value={channel}>
                    {channel}
                  </option>
                ))}
              </Select>
              <Select
                label="Initial Status"
                value={templateStatus}
                onChange={(event) => setTemplateStatus(event.target.value as CampaignTemplateStatus)}
              >
                <option value="draft">draft</option>
                <option value="approved">approved</option>
                <option value="archived">archived</option>
              </Select>
            </div>
            <Textarea
              label="Template Content"
              rows={4}
              placeholder="Hi {{name}}, your cart is waiting."
              value={templateContent}
              onChange={(event) => setTemplateContent(event.target.value)}
            />
            <Button
              type="button"
              loading={createTemplateMutation.isPending}
              disabled={templateName.trim().length < 2 || templateContent.trim().length < 1}
              onClick={() => createTemplateMutation.mutate()}
            >
              Save Template
            </Button>
          </div>

          <div className="mt-4 space-y-2">
            {!templates.length ? (
              <EmptyState title="No templates yet" description="Create approved templates before send_now campaigns." />
            ) : (
              templates.map((template) => (
                <article key={template.id} className="rounded-xl border border-surface-100 bg-surface-50 p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="font-semibold text-surface-700">{template.name}</p>
                    <div className="flex items-center gap-2">
                      <Badge variant="info">{template.channel}</Badge>
                      <Badge
                        variant={
                          template.status === "approved"
                            ? "positive"
                            : template.status === "archived"
                              ? "neutral"
                              : "info"
                        }
                      >
                        {template.status}
                      </Badge>
                    </div>
                  </div>
                  <p className="mt-1 text-xs text-surface-500">{template.content}</p>
                  <div className="mt-2 flex items-center justify-between gap-2">
                    <p className="text-xs text-surface-500">Updated: {formatDateTime(template.updated_at)}</p>
                    {template.status === "draft" ? (
                      <Button
                        type="button"
                        size="sm"
                        variant="secondary"
                        loading={
                          approveTemplateMutation.isPending &&
                          approveTemplateMutation.variables === template.id
                        }
                        onClick={() => approveTemplateMutation.mutate(template.id)}
                      >
                        Approve
                      </Button>
                    ) : null}
                  </div>
                </article>
              ))
            )}
          </div>
        </Card>
      </div>

      <Card>
        <h3 className="font-heading text-lg font-bold text-surface-800">Campaign Composer</h3>
        <div className="mt-4 grid gap-3 lg:grid-cols-5">
          <Input
            label="Campaign Name"
            value={campaignName}
            onChange={(event) => setCampaignName(event.target.value)}
            placeholder="Winback - Week 1"
          />
          <Select
            label="Segment"
            value={campaignSegmentId}
            onChange={(event) => setCampaignSegmentId(event.target.value)}
          >
            <option value="">All customers</option>
            {segments.map((segment) => (
              <option key={segment.id} value={segment.id}>
                {segment.name}
              </option>
            ))}
          </Select>
          <Select
            label="Template"
            value={campaignTemplateId}
            onChange={(event) => setCampaignTemplateId(event.target.value)}
          >
            <option value="">No template</option>
            {templates.map((template) => (
              <option key={template.id} value={template.id}>
                {template.name} ({template.status})
              </option>
            ))}
          </Select>
          <Select
            label="Channel"
            value={campaignChannel}
            onChange={(event) => setCampaignChannel(event.target.value as CampaignChannel)}
          >
            {CHANNEL_OPTIONS.map((channel) => (
              <option key={channel} value={channel}>
                {channel}
              </option>
            ))}
          </Select>
          <Select
            label="Send Mode"
            value={campaignSendNow ? "send_now" : "queue_only"}
            onChange={(event) => setCampaignSendNow(event.target.value === "send_now")}
          >
            <option value="send_now">Send now</option>
            <option value="queue_only">Queue only</option>
          </Select>
        </div>
        <div className="mt-3">
          <Button
            type="button"
            loading={createCampaignMutation.isPending}
            disabled={!canCreateCampaign}
            onClick={() => createCampaignMutation.mutate()}
          >
            Create Campaign
          </Button>
        </div>

        <div className="mt-6 grid gap-3 md:grid-cols-3">
          <Select
            label="Status Filter"
            value={campaignStatusFilter}
            onChange={(event) => setCampaignStatusFilter(event.target.value as "" | CampaignStatus)}
          >
            <option value="">All statuses</option>
            <option value="draft">draft</option>
            <option value="queued">queued</option>
            <option value="sending">sending</option>
            <option value="completed">completed</option>
            <option value="failed">failed</option>
            <option value="cancelled">cancelled</option>
          </Select>
          <div className="mt-7">
            <Badge variant="info">{campaignsQuery.data.pagination.total} campaigns</Badge>
          </div>
        </div>

        {!campaigns.length ? (
          <div className="mt-3">
            <EmptyState title="No campaigns yet" description="Create and dispatch your first campaign." />
          </div>
        ) : (
          <div className="mt-3 space-y-2">
            {campaigns.map((campaign: CampaignOut) => (
              <article
                key={campaign.id}
                className={`rounded-xl border p-3 ${
                  selectedCampaignId === campaign.id
                    ? "border-cobalt-400 bg-cobalt-50"
                    : "border-surface-100 bg-surface-50"
                }`}
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <p className="font-semibold text-surface-700">{campaign.name}</p>
                    <p className="text-xs text-surface-500">
                      {campaign.channel} | recipients: {campaign.total_recipients} | sent: {campaign.sent_count} |
                      suppressed: {campaign.suppressed_count}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge variant="info">{campaign.status}</Badge>
                    <Button type="button" size="sm" variant="ghost" onClick={() => setSelectedCampaignId(campaign.id)}>
                      Recipients
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      variant="secondary"
                      loading={
                        dispatchCampaignMutation.isPending &&
                        dispatchCampaignMutation.variables === campaign.id
                      }
                      onClick={() => dispatchCampaignMutation.mutate(campaign.id)}
                    >
                      Dispatch
                    </Button>
                  </div>
                </div>
                <p className="mt-1 text-xs text-surface-500">Updated: {formatDateTime(campaign.updated_at)}</p>
              </article>
            ))}

            <PaginationControls
              pagination={campaignsQuery.data.pagination}
              pageSize={campaignPageSize}
              onPageSizeChange={(size) => {
                setCampaignPageSize(size);
                setCampaignPage(1);
              }}
              onPrev={() => setCampaignPage((value) => Math.max(1, value - 1))}
              onNext={() => {
                if (campaignsQuery.data.pagination.has_next) {
                  setCampaignPage((value) => value + 1);
                }
              }}
            />
          </div>
        )}
      </Card>

      {selectedCampaign ? (
        <Card>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h3 className="font-heading text-lg font-bold text-surface-800">
                Recipients: {selectedCampaign.name}
              </h3>
              <p className="text-xs text-surface-500">Campaign ID: {selectedCampaign.id}</p>
            </div>
            <Select
              value={recipientStatusFilter}
              onChange={(event) =>
                setRecipientStatusFilter(event.target.value as "" | CampaignRecipientStatus)
              }
              className="w-56"
            >
              <option value="">All statuses</option>
              <option value="queued">queued</option>
              <option value="sent">sent</option>
              <option value="failed">failed</option>
              <option value="suppressed">suppressed</option>
              <option value="skipped">skipped</option>
            </Select>
          </div>
          <div className="mt-3">
            {recipientsQuery.isLoading ? (
              <LoadingState label="Loading recipients..." />
            ) : recipientsQuery.isError || !recipientsQuery.data ? (
              <ErrorState message="Could not load campaign recipients." onRetry={() => recipientsQuery.refetch()} />
            ) : !recipientsQuery.data.items.length ? (
              <EmptyState title="No recipients" description="This campaign currently has no recipients." />
            ) : (
              <div className="space-y-2">
                {recipientsQuery.data.items.map((recipient) => (
                  <article key={recipient.id} className="rounded-xl border border-surface-100 bg-surface-50 p-3">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="font-semibold text-surface-700">{recipient.recipient}</p>
                      <Badge variant="info">{recipient.status}</Badge>
                    </div>
                    <p className="mt-1 text-xs text-surface-500">Customer ID: {recipient.customer_id}</p>
                    {recipient.error_message ? (
                      <p className="mt-1 text-xs text-red-600">Error: {recipient.error_message}</p>
                    ) : null}
                  </article>
                ))}
              </div>
            )}
          </div>
        </Card>
      ) : null}

      <div className="grid gap-6 xl:grid-cols-2">
        <Card>
          <h3 className="font-heading text-lg font-bold text-surface-800">Consent and Opt-out</h3>
          <div className="mt-4 grid gap-3">
            <Input
              label="Customer ID"
              value={consentCustomerId}
              onChange={(event) => setConsentCustomerId(event.target.value)}
              placeholder="Paste customer ID"
            />
            <div className="grid gap-3 sm:grid-cols-3">
              <Select
                label="Channel"
                value={consentChannel}
                onChange={(event) => setConsentChannel(event.target.value as CampaignChannel)}
              >
                {CHANNEL_OPTIONS.map((channel) => (
                  <option key={channel} value={channel}>
                    {channel}
                  </option>
                ))}
              </Select>
              <Select
                label="Status"
                value={consentStatus}
                onChange={(event) => setConsentStatus(event.target.value as "subscribed" | "unsubscribed")}
              >
                <option value="subscribed">subscribed</option>
                <option value="unsubscribed">unsubscribed</option>
              </Select>
              <Input
                label="Source"
                value={consentSource}
                onChange={(event) => setConsentSource(event.target.value)}
              />
            </div>
            <Button
              type="button"
              loading={upsertConsentMutation.isPending}
              disabled={consentCustomerId.trim().length < 5}
              onClick={() => upsertConsentMutation.mutate()}
            >
              Save Consent
            </Button>
          </div>

          <div className="mt-4 space-y-2">
            {!consents.length ? (
              <EmptyState title="No consent records" description="Updates will appear here after first save." />
            ) : (
              consents.map((consent) => (
                <article key={consent.id} className="rounded-xl border border-surface-100 bg-surface-50 p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="font-semibold text-surface-700">{consent.customer_id}</p>
                    <Badge variant={consent.status === "subscribed" ? "positive" : "negative"}>
                      {consent.status}
                    </Badge>
                  </div>
                  <p className="mt-1 text-xs text-surface-500">
                    {consent.channel} | updated {formatDateTime(consent.updated_at)}
                  </p>
                </article>
              ))
            )}

            <PaginationControls
              pagination={consentsQuery.data.pagination}
              pageSize={consentPageSize}
              onPageSizeChange={(size) => {
                setConsentPageSize(size);
                setConsentPage(1);
              }}
              onPrev={() => setConsentPage((value) => Math.max(1, value - 1))}
              onNext={() => {
                if (consentsQuery.data.pagination.has_next) {
                  setConsentPage((value) => value + 1);
                }
              }}
            />
          </div>
        </Card>

        <Card>
          <h3 className="font-heading text-lg font-bold text-surface-800">Retention Triggers</h3>
          <div className="mt-4 grid gap-3">
            <Input
              label="Trigger Name"
              placeholder="Repeat Purchase Nudge"
              value={triggerName}
              onChange={(event) => setTriggerName(event.target.value)}
            />
            <div className="grid gap-3 sm:grid-cols-2">
              <Select
                label="Segment"
                value={triggerSegmentId}
                onChange={(event) => setTriggerSegmentId(event.target.value)}
              >
                <option value="">All customers</option>
                {segments.map((segment) => (
                  <option key={segment.id} value={segment.id}>
                    {segment.name}
                  </option>
                ))}
              </Select>
              <Select
                label="Template"
                value={triggerTemplateId}
                onChange={(event) => setTriggerTemplateId(event.target.value)}
              >
                <option value="">No template</option>
                {templates.map((template) => (
                  <option key={template.id} value={template.id}>
                    {template.name}
                  </option>
                ))}
              </Select>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <Select
                label="Channel"
                value={triggerChannel}
                onChange={(event) => setTriggerChannel(event.target.value as CampaignChannel)}
              >
                {CHANNEL_OPTIONS.map((channel) => (
                  <option key={channel} value={channel}>
                    {channel}
                  </option>
                ))}
              </Select>
              <Select
                label="Run Mode"
                value={triggerAutoDispatch ? "auto_dispatch" : "queue_only"}
                onChange={(event) => setTriggerAutoDispatch(event.target.value === "auto_dispatch")}
              >
                <option value="auto_dispatch">Auto dispatch on run</option>
                <option value="queue_only">Queue only on run</option>
              </Select>
            </div>
            <Button
              type="button"
              loading={createTriggerMutation.isPending}
              disabled={triggerName.trim().length < 2}
              onClick={() => createTriggerMutation.mutate()}
            >
              Save Trigger
            </Button>
          </div>

          <div className="mt-4 space-y-2">
            {!triggers.length ? (
              <EmptyState title="No triggers yet" description="Create retention triggers to automate repeat outreach." />
            ) : (
              triggers.map((trigger) => (
                <article key={trigger.id} className="rounded-xl border border-surface-100 bg-surface-50 p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <p className="font-semibold text-surface-700">{trigger.name}</p>
                      <p className="text-xs text-surface-500">
                        {trigger.trigger_type} | {trigger.channel}
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge variant={trigger.status === "active" ? "positive" : "neutral"}>
                        {trigger.status}
                      </Badge>
                      <Button
                        type="button"
                        size="sm"
                        variant="secondary"
                        loading={runTriggerMutation.isPending && runTriggerMutation.variables === trigger.id}
                        onClick={() => runTriggerMutation.mutate(trigger.id)}
                      >
                        Run now
                      </Button>
                    </div>
                  </div>
                  <p className="mt-1 text-xs text-surface-500">
                    Last run: {trigger.last_run_at ? formatDateTime(trigger.last_run_at) : "Never"}
                  </p>
                </article>
              ))
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}
