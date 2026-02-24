import axios from "axios";
import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ExternalLink, Globe } from "lucide-react";
import { Link } from "react-router-dom";
import { storefrontService } from "../api/services";
import type { StorefrontConfigUpsertIn } from "../api/types";
import { LoadingState } from "../components/state/loading-state";
import { ErrorState } from "../components/state/error-state";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { Textarea } from "../components/ui/textarea";
import { useToast } from "../hooks/use-toast";
import { getApiErrorMessage } from "../lib/api-error";
import { formatDateTime } from "../lib/format";

interface StorefrontFormState {
  slug: string;
  display_name: string;
  tagline: string;
  description: string;
  seo_title: string;
  seo_description: string;
  seo_og_image_url: string;
  logo_url: string;
  accent_color: string;
  hero_image_url: string;
  support_email: string;
  support_phone: string;
  policy_shipping: string;
  policy_returns: string;
  policy_privacy: string;
  custom_domain: string;
  is_published: boolean;
}

function normalizeOptional(value: string) {
  const cleaned = value.trim();
  return cleaned || undefined;
}

export function StorefrontSettingsPage() {
  const queryClient = useQueryClient();
  const { showToast } = useToast();
  const [verificationToken, setVerificationToken] = useState("");
  const [form, setForm] = useState<StorefrontFormState>({
    slug: "",
    display_name: "",
    tagline: "",
    description: "",
    seo_title: "",
    seo_description: "",
    seo_og_image_url: "",
    logo_url: "",
    accent_color: "#16a34a",
    hero_image_url: "",
    support_email: "",
    support_phone: "",
    policy_shipping: "",
    policy_returns: "",
    policy_privacy: "",
    custom_domain: "",
    is_published: false
  });

  const configQuery = useQuery({
    queryKey: ["storefront", "config"],
    queryFn: storefrontService.getConfig,
    retry: false
  });

  const configNotFound =
    configQuery.isError &&
    axios.isAxiosError(configQuery.error) &&
    configQuery.error.response?.status === 404;

  const domainStatusQuery = useQuery({
    queryKey: ["storefront", "domain-status"],
    queryFn: storefrontService.getDomainStatus,
    enabled: !configNotFound && !!configQuery.data
  });

  useEffect(() => {
    if (!configQuery.data) return;
    setForm({
      slug: configQuery.data.slug ?? "",
      display_name: configQuery.data.display_name ?? "",
      tagline: configQuery.data.tagline ?? "",
      description: configQuery.data.description ?? "",
      seo_title: configQuery.data.seo_title ?? "",
      seo_description: configQuery.data.seo_description ?? "",
      seo_og_image_url: configQuery.data.seo_og_image_url ?? "",
      logo_url: configQuery.data.logo_url ?? "",
      accent_color: configQuery.data.accent_color ?? "#16a34a",
      hero_image_url: configQuery.data.hero_image_url ?? "",
      support_email: configQuery.data.support_email ?? "",
      support_phone: configQuery.data.support_phone ?? "",
      policy_shipping: configQuery.data.policy_shipping ?? "",
      policy_returns: configQuery.data.policy_returns ?? "",
      policy_privacy: configQuery.data.policy_privacy ?? "",
      custom_domain: configQuery.data.custom_domain ?? "",
      is_published: configQuery.data.is_published
    });
  }, [configQuery.data]);

  const saveMutation = useMutation({
    mutationFn: (payload: StorefrontConfigUpsertIn) => storefrontService.upsertConfig(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["storefront", "config"] });
      queryClient.invalidateQueries({ queryKey: ["storefront", "domain-status"] });
      showToast({
        title: "Storefront saved",
        description: "Storefront and SEO settings updated.",
        variant: "success"
      });
    },
    onError: (error) => {
      showToast({
        title: "Failed to save storefront",
        description: getApiErrorMessage(error),
        variant: "error"
      });
    }
  });

  const challengeMutation = useMutation({
    mutationFn: storefrontService.createDomainChallenge,
    onSuccess: (payload) => {
      queryClient.invalidateQueries({ queryKey: ["storefront", "domain-status"] });
      setVerificationToken(payload.txt_record_value);
      showToast({
        title: "DNS challenge generated",
        description: "Add the TXT record to your DNS provider and verify.",
        variant: "success"
      });
    },
    onError: (error) => {
      showToast({
        title: "Failed to generate challenge",
        description: getApiErrorMessage(error),
        variant: "error"
      });
    }
  });

  const verifyMutation = useMutation({
    mutationFn: storefrontService.verifyDomain,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["storefront", "domain-status"] });
      showToast({
        title: "Domain verified",
        description: "Custom domain is now marked as verified.",
        variant: "success"
      });
    },
    onError: (error) => {
      showToast({
        title: "Domain verification failed",
        description: getApiErrorMessage(error),
        variant: "error"
      });
    }
  });

  const publicStoreUrl = useMemo(() => {
    const cleaned = form.slug.trim();
    return cleaned ? `/store/${cleaned}` : "";
  }, [form.slug]);

  if (configQuery.isLoading) {
    return <LoadingState label="Loading storefront settings..." />;
  }

  if (configQuery.isError && !configNotFound) {
    return (
      <ErrorState
        message="Unable to load storefront settings."
        onRetry={() => configQuery.refetch()}
      />
    );
  }

  return (
    <div className="space-y-6">
      <Card className="animate-fade-up bg-[linear-gradient(135deg,#132a42_0%,#20496c_55%,#2e5778_100%)] text-white">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-[0.28em] text-white/70">Storefront Studio</p>
            <h2 className="mt-2 font-heading text-2xl font-black">Hosted Storefront Configuration</h2>
            <p className="mt-1 text-sm text-white/80">
              Manage publish visibility, custom domain verification, and SEO metadata.
            </p>
          </div>
          {publicStoreUrl ? (
            <Link
              to={publicStoreUrl}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-2 rounded-lg bg-white/15 px-3 py-2 text-sm font-semibold text-white transition hover:bg-white/25"
            >
              Open Storefront <ExternalLink className="h-4 w-4" />
            </Link>
          ) : null}
        </div>
      </Card>

      <Card className="animate-fade-up [animation-delay:50ms]">
        <h3 className="font-heading text-lg font-bold text-surface-800">Store Basics</h3>
        <p className="mt-1 text-sm text-surface-500">
          These values power the public store profile and listing page.
        </p>
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          <Input
            label="Store Slug"
            value={form.slug}
            onChange={(event) => setForm((prev) => ({ ...prev, slug: event.target.value }))}
            placeholder="ankara-house"
          />
          <Input
            label="Display Name"
            value={form.display_name}
            onChange={(event) => setForm((prev) => ({ ...prev, display_name: event.target.value }))}
            placeholder="Ankara House"
          />
          <Input
            label="Accent Color"
            value={form.accent_color}
            onChange={(event) => setForm((prev) => ({ ...prev, accent_color: event.target.value }))}
            placeholder="#16a34a"
          />
          <Input
            label="Custom Domain"
            value={form.custom_domain}
            onChange={(event) => setForm((prev) => ({ ...prev, custom_domain: event.target.value }))}
            placeholder="shop.example.com"
          />
          <Input
            label="Support Email"
            value={form.support_email}
            onChange={(event) => setForm((prev) => ({ ...prev, support_email: event.target.value }))}
            placeholder="support@example.com"
          />
          <Input
            label="Support Phone"
            value={form.support_phone}
            onChange={(event) => setForm((prev) => ({ ...prev, support_phone: event.target.value }))}
            placeholder="+2348011112222"
          />
          <Input
            label="Logo URL"
            value={form.logo_url}
            onChange={(event) => setForm((prev) => ({ ...prev, logo_url: event.target.value }))}
            placeholder="https://cdn.example.com/logo.png"
          />
          <Input
            label="Hero Image URL"
            value={form.hero_image_url}
            onChange={(event) => setForm((prev) => ({ ...prev, hero_image_url: event.target.value }))}
            placeholder="https://cdn.example.com/hero.png"
          />
        </div>
        <div className="mt-3 grid gap-3 md:grid-cols-2">
          <Textarea
            label="Tagline"
            rows={2}
            value={form.tagline}
            onChange={(event) => setForm((prev) => ({ ...prev, tagline: event.target.value }))}
          />
          <Textarea
            label="Description"
            rows={2}
            value={form.description}
            onChange={(event) => setForm((prev) => ({ ...prev, description: event.target.value }))}
          />
        </div>
        <label className="mt-4 inline-flex items-center gap-2 text-sm font-semibold text-surface-700">
          <input
            type="checkbox"
            checked={form.is_published}
            onChange={(event) => setForm((prev) => ({ ...prev, is_published: event.target.checked }))}
          />
          Publish storefront publicly
        </label>
      </Card>

      <Card className="animate-fade-up [animation-delay:80ms]">
        <h3 className="font-heading text-lg font-bold text-surface-800">SEO Controls</h3>
        <p className="mt-1 text-sm text-surface-500">
          Configure title and metadata used for search and social previews.
        </p>
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          <Input
            label="SEO Title"
            value={form.seo_title}
            onChange={(event) => setForm((prev) => ({ ...prev, seo_title: event.target.value }))}
            placeholder="Ankara House | Premium Fabrics"
          />
          <Input
            label="SEO OG Image URL"
            value={form.seo_og_image_url}
            onChange={(event) => setForm((prev) => ({ ...prev, seo_og_image_url: event.target.value }))}
            placeholder="https://cdn.example.com/og-cover.jpg"
          />
          <div className="md:col-span-2">
            <Textarea
              label="SEO Description"
              rows={3}
              value={form.seo_description}
              onChange={(event) => setForm((prev) => ({ ...prev, seo_description: event.target.value }))}
              placeholder="Shop premium fabrics and get fast nationwide delivery."
            />
          </div>
        </div>
      </Card>

      <Card className="animate-fade-up [animation-delay:110ms]">
        <h3 className="font-heading text-lg font-bold text-surface-800">Store Policies</h3>
        <div className="mt-4 grid gap-3 md:grid-cols-3">
          <Textarea
            label="Shipping Policy"
            rows={4}
            value={form.policy_shipping}
            onChange={(event) => setForm((prev) => ({ ...prev, policy_shipping: event.target.value }))}
          />
          <Textarea
            label="Returns Policy"
            rows={4}
            value={form.policy_returns}
            onChange={(event) => setForm((prev) => ({ ...prev, policy_returns: event.target.value }))}
          />
          <Textarea
            label="Privacy Policy"
            rows={4}
            value={form.policy_privacy}
            onChange={(event) => setForm((prev) => ({ ...prev, policy_privacy: event.target.value }))}
          />
        </div>
        <div className="mt-4 flex justify-end">
          <Button
            type="button"
            loading={saveMutation.isPending}
            onClick={() =>
              saveMutation.mutate({
                slug: form.slug.trim(),
                display_name: form.display_name.trim(),
                tagline: normalizeOptional(form.tagline),
                description: normalizeOptional(form.description),
                seo_title: normalizeOptional(form.seo_title),
                seo_description: normalizeOptional(form.seo_description),
                seo_og_image_url: normalizeOptional(form.seo_og_image_url),
                logo_url: normalizeOptional(form.logo_url),
                accent_color: normalizeOptional(form.accent_color),
                hero_image_url: normalizeOptional(form.hero_image_url),
                support_email: normalizeOptional(form.support_email),
                support_phone: normalizeOptional(form.support_phone),
                policy_shipping: normalizeOptional(form.policy_shipping),
                policy_returns: normalizeOptional(form.policy_returns),
                policy_privacy: normalizeOptional(form.policy_privacy),
                custom_domain: normalizeOptional(form.custom_domain) ?? null,
                is_published: form.is_published
              })
            }
          >
            Save Storefront Settings
          </Button>
        </div>
      </Card>

      <Card className="animate-fade-up [animation-delay:140ms]">
        <div className="flex items-center justify-between gap-3">
          <h3 className="font-heading text-lg font-bold text-surface-800">Custom Domain Verification</h3>
          <Badge
            variant={
              domainStatusQuery.data?.verification_status === "verified"
                ? "positive"
                : domainStatusQuery.data?.verification_status === "pending"
                  ? "info"
                  : "neutral"
            }
          >
            {domainStatusQuery.data?.verification_status ?? "not_configured"}
          </Badge>
        </div>
        <p className="mt-1 text-sm text-surface-500">
          Generate DNS TXT challenge, add it to your domain provider, then verify.
        </p>

        <div className="mt-4 grid gap-3 sm:grid-cols-3">
          <Button
            type="button"
            variant="secondary"
            loading={challengeMutation.isPending}
            onClick={() => challengeMutation.mutate()}
            disabled={!configQuery.data && !form.slug.trim()}
          >
            Generate Challenge
          </Button>
          <Input
            label="Verification Token or TXT Value"
            value={verificationToken}
            onChange={(event) => setVerificationToken(event.target.value)}
            placeholder="monidesk-site-verification=..."
          />
          <div className="flex items-end">
            <Button
              type="button"
              loading={verifyMutation.isPending}
              onClick={() =>
                verifyMutation.mutate({
                  verification_token: verificationToken.trim()
                })
              }
              disabled={!verificationToken.trim()}
            >
              Verify Domain
            </Button>
          </div>
        </div>

        {domainStatusQuery.data ? (
          <div className="mt-4 rounded-xl border border-surface-100 bg-surface-50 p-4 text-sm text-surface-600">
            <p className="flex items-center gap-2 font-semibold text-surface-700">
              <Globe className="h-4 w-4" />
              {domainStatusQuery.data.custom_domain ?? "No custom domain configured"}
            </p>
            <p className="mt-2">
              Status: <span className="font-semibold">{domainStatusQuery.data.verification_status}</span>
            </p>
            {domainStatusQuery.data.txt_record_name ? (
              <p className="mt-1">
                TXT Name: <code>{domainStatusQuery.data.txt_record_name}</code>
              </p>
            ) : null}
            {domainStatusQuery.data.txt_record_value ? (
              <p className="mt-1">
                TXT Value: <code>{domainStatusQuery.data.txt_record_value}</code>
              </p>
            ) : null}
            {domainStatusQuery.data.domain_last_checked_at ? (
              <p className="mt-1">Last Checked: {formatDateTime(domainStatusQuery.data.domain_last_checked_at)}</p>
            ) : null}
            {domainStatusQuery.data.domain_verified_at ? (
              <p className="mt-1">Verified At: {formatDateTime(domainStatusQuery.data.domain_verified_at)}</p>
            ) : null}
          </div>
        ) : null}
      </Card>
    </div>
  );
}
