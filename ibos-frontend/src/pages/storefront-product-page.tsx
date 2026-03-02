import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { checkoutService, storefrontService } from "../api/services";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Select } from "../components/ui/select";
import { Textarea } from "../components/ui/textarea";
import { LoadingState } from "../components/state/loading-state";
import { ErrorState } from "../components/state/error-state";
import { EmptyState } from "../components/state/empty-state";
import { useToast } from "../hooks/use-toast";
import { getApiErrorMessage } from "../lib/api-error";
import { formatCurrency } from "../lib/format";

function setMetaDescription(description: string | null | undefined) {
  const next = description ?? "";
  const meta = document.querySelector("meta[name='description']");
  if (meta) {
    meta.setAttribute("content", next);
    return;
  }
  const newMeta = document.createElement("meta");
  newMeta.setAttribute("name", "description");
  newMeta.setAttribute("content", next);
  document.head.appendChild(newMeta);
}

export function StorefrontProductPage() {
  const params = useParams();
  const { showToast } = useToast();
  const slug = params.slug ?? "";
  const productId = params.productId ?? "";
  const [selectedVariantId, setSelectedVariantId] = useState("");
  const [qty, setQty] = useState(1);
  const [paymentMethod, setPaymentMethod] = useState<"cash" | "transfer" | "pos">("transfer");
  const [note, setNote] = useState("");
  const [checkoutResult, setCheckoutResult] = useState<{
    sessionToken: string;
    paymentCheckoutUrl?: string | null;
    orderId: string;
    orderStatus: string;
    totalAmount: number;
  } | null>(null);

  const storefrontQuery = useQuery({
    queryKey: ["storefront", "public", slug],
    enabled: Boolean(slug),
    queryFn: () => storefrontService.getPublicStorefront(slug)
  });

  const productQuery = useQuery({
    queryKey: ["storefront", "public-product", slug, productId],
    enabled: Boolean(slug && productId),
    queryFn: () => storefrontService.getPublicProductDetail(slug, productId)
  });

  useEffect(() => {
    if (!productQuery.data || !storefrontQuery.data) return;
    document.title = `${productQuery.data.name} | ${storefrontQuery.data.display_name}`;
    setMetaDescription(
      storefrontQuery.data.seo_description ||
        productQuery.data.description ||
        storefrontQuery.data.description
    );
  }, [productQuery.data, storefrontQuery.data]);

  useEffect(() => {
    if (!productQuery.data?.variants.length) return;
    if (!selectedVariantId) {
      setSelectedVariantId(productQuery.data.variants[0].id);
    }
  }, [productQuery.data, selectedVariantId]);

  const selectedVariant = useMemo(
    () => productQuery.data?.variants.find((variant) => variant.id === selectedVariantId) ?? null,
    [productQuery.data, selectedVariantId]
  );

  const checkoutMutation = useMutation({
    mutationFn: async () => {
      const variantId = selectedVariantId.trim();
      if (!variantId) {
        throw new Error("Select a variant to continue.");
      }
      if (!selectedVariant || selectedVariant.selling_price == null) {
        throw new Error("Selected variant has no checkout price.");
      }
      const quantity = Number(qty || 0);
      if (!Number.isFinite(quantity) || quantity < 1) {
        throw new Error("Quantity must be at least 1.");
      }

      const session = await checkoutService.createStorefrontSession(slug, {
        variant_id: variantId,
        qty: quantity,
        payment_method: paymentMethod,
        channel: "instagram",
        note: note.trim() || undefined,
        success_redirect_url: window.location.href,
        cancel_redirect_url: window.location.href
      });
      const placed = await checkoutService.placePublicOrder(session.session_token, {
        payment_method: paymentMethod,
        note: note.trim() || undefined
      });
      return { session, placed };
    },
    onSuccess: ({ session, placed }) => {
      setCheckoutResult({
        sessionToken: session.session_token,
        paymentCheckoutUrl: session.payment_checkout_url,
        orderId: placed.order_id,
        orderStatus: placed.order_status,
        totalAmount: placed.total_amount
      });
      showToast({
        title: "Checkout initiated",
        description: "Order created. Continue to payment to complete the purchase.",
        variant: "success"
      });
    },
    onError: (error) => {
      showToast({
        title: "Could not start checkout",
        description: getApiErrorMessage(error),
        variant: "error"
      });
    }
  });

  if (storefrontQuery.isLoading || productQuery.isLoading) {
    return <LoadingState label="Loading product..." />;
  }

  if (storefrontQuery.isError || productQuery.isError || !storefrontQuery.data || !productQuery.data) {
    return (
      <ErrorState
        message="Unable to load product details."
        onRetry={() => {
          storefrontQuery.refetch();
          productQuery.refetch();
        }}
      />
    );
  }

  const storefront = storefrontQuery.data;
  const product = productQuery.data;

  return (
    <div className="min-h-screen bg-[linear-gradient(180deg,#f7fbff_0%,#ecf3f8_100%)] px-4 py-8 dark:bg-[linear-gradient(180deg,#0f2238_0%,#132b45_100%)] sm:px-8">
      <div className="mx-auto max-w-4xl space-y-6">
        <Link
          to={`/store/${slug}`}
          className="inline-flex items-center gap-2 text-sm font-semibold text-cobalt-700 transition hover:text-cobalt-800"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Store
        </Link>

        <Card className="overflow-hidden border-0 bg-[linear-gradient(140deg,#152e48_0%,#214563_50%,#2d4f68_100%)] text-white">
          <div className="space-y-3 p-6 sm:p-8">
            <p className="text-xs uppercase tracking-[0.28em] text-white/70">{storefront.display_name}</p>
            <h1 className="font-heading text-3xl font-black">{product.name}</h1>
            <p className="text-sm text-white/80">{product.category ?? "General category"}</p>
            {product.description ? <p className="text-sm text-white/75">{product.description}</p> : null}
          </div>
        </Card>

        <Card>
          <h2 className="font-heading text-xl font-bold text-surface-800">Available Variants</h2>
          {product.variants.length === 0 ? (
            <EmptyState title="No variants available" description="This product has no published variants." />
          ) : (
            <div className="mt-4 space-y-3">
              {product.variants.map((variant) => (
                <article
                  key={variant.id}
                  className="rounded-xl border border-surface-100 bg-surface-50 p-4"
                >
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <p className="text-sm font-bold text-surface-800">{variant.label ?? "Standard Variant"}</p>
                      <p className="text-xs text-surface-500">Size: {variant.size}</p>
                      {variant.sku ? <p className="text-xs text-surface-500">SKU: {variant.sku}</p> : null}
                    </div>
                    <p className="font-heading text-lg font-black text-surface-800">
                      {variant.selling_price != null ? formatCurrency(variant.selling_price) : "Price on request"}
                    </p>
                  </div>
                </article>
              ))}
            </div>
          )}
        </Card>

        <Card>
          <h3 className="font-heading text-lg font-bold text-surface-800">Checkout</h3>
          <p className="mt-2 text-sm text-surface-500">
            Select your variant and quantity, then create your order to continue to payment.
          </p>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            <Select
              label="Variant"
              value={selectedVariantId}
              onChange={(event) => setSelectedVariantId(event.target.value)}
            >
              {product.variants.map((variant) => (
                <option key={variant.id} value={variant.id}>
                  {variant.label ?? "Standard"} - {variant.size}
                  {variant.selling_price != null ? ` (${formatCurrency(variant.selling_price)})` : ""}
                </option>
              ))}
            </Select>
            <Input
              label="Quantity"
              type="number"
              min={1}
              value={qty}
              onChange={(event) => setQty(Number(event.target.value || 1))}
            />
            <Select
              label="Payment Method"
              value={paymentMethod}
              onChange={(event) => setPaymentMethod(event.target.value as "cash" | "transfer" | "pos")}
            >
              <option value="transfer">Transfer</option>
              <option value="pos">POS</option>
              <option value="cash">Cash</option>
            </Select>
            <div className="rounded-lg border border-surface-100 bg-surface-50 p-3 text-sm">
              <p className="text-surface-500">Estimated Total</p>
              <p className="mt-1 text-lg font-black text-surface-800">
                {selectedVariant?.selling_price != null
                  ? formatCurrency(selectedVariant.selling_price * Math.max(1, Number(qty || 1)))
                  : "Price unavailable"}
              </p>
            </div>
          </div>
          <div className="mt-3">
            <Textarea
              label="Order Note (optional)"
              rows={3}
              value={note}
              onChange={(event) => setNote(event.target.value)}
              placeholder="Special instructions, delivery notes, preferred contact time..."
            />
          </div>
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <Button
              type="button"
              loading={checkoutMutation.isPending}
              onClick={() => checkoutMutation.mutate()}
              disabled={!selectedVariantId || selectedVariant?.selling_price == null}
            >
              Start Checkout
            </Button>
            {checkoutResult?.paymentCheckoutUrl ? (
              <a
                href={checkoutResult.paymentCheckoutUrl}
                target="_blank"
                rel="noreferrer"
                className="inline-flex h-10 items-center justify-center rounded-lg bg-[linear-gradient(140deg,#27c25c,#14823f)] px-4 text-sm font-semibold text-white transition hover:brightness-110"
              >
                Continue to Payment
              </a>
            ) : null}
          </div>
          {checkoutResult ? (
            <div className="mt-4 rounded-lg border border-mint-200 bg-mint-50 p-3 text-sm text-mint-800">
              <p className="font-semibold">Order created successfully</p>
              <p className="mt-1">Order ID: {checkoutResult.orderId}</p>
              <p>Order Status: {checkoutResult.orderStatus}</p>
              <p>Checkout Token: {checkoutResult.sessionToken}</p>
              <p>Total: {formatCurrency(checkoutResult.totalAmount)}</p>
            </div>
          ) : null}
          <div className="mt-4 border-t border-surface-100 pt-3 text-sm text-surface-500">
            <p className="font-semibold text-surface-700">Need help?</p>
            <p>Email: {storefront.support_email ?? "Not provided"}</p>
            <p>Phone: {storefront.support_phone ?? "Not provided"}</p>
          </div>
        </Card>
      </div>
    </div>
  );
}
