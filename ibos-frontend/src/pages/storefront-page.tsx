import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import {
  authService,
  checkoutService,
  storefrontService,
} from "../api/services";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Modal } from "../components/ui/modal";
import { Select } from "../components/ui/select";
import { Textarea } from "../components/ui/textarea";
import { PaginationControls } from "../components/ui/pagination-controls";
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

export function StorefrontPage() {
  const params = useParams();
  const { showToast } = useToast();
  const profileQuery = useQuery({
    queryKey: ["auth", "me"],
    queryFn: authService.me,
  });
  const slug = params.slug ?? "";
  const [q, setQ] = useState("");
  const [category, setCategory] = useState("");
  const [offset, setOffset] = useState(0);
  const [buyNowProductId, setBuyNowProductId] = useState<string | null>(null);
  const [buyNowProductName, setBuyNowProductName] = useState("");
  const [selectedVariantId, setSelectedVariantId] = useState("");
  const [qty, setQty] = useState(1);
  const [paymentMethod, setPaymentMethod] = useState<
    "cash" | "transfer" | "pos"
  >("transfer");
  const [note, setNote] = useState("");
  const [checkoutResult, setCheckoutResult] = useState<{
    paymentCheckoutUrl?: string | null;
    orderId: string;
    orderStatus: string;
    totalAmount: number;
  } | null>(null);
  const limit = 24;

  useEffect(() => {
    setOffset(0);
  }, [q, category, slug]);

  const storefrontQuery = useQuery({
    queryKey: ["storefront", "public", slug],
    enabled: Boolean(slug),
    queryFn: () => storefrontService.getPublicStorefront(slug),
  });

  const productsQuery = useQuery({
    queryKey: [
      "storefront",
      "public-products",
      slug,
      q,
      category,
      limit,
      offset,
    ],
    enabled: Boolean(slug),
    queryFn: () =>
      storefrontService.listPublicProducts(slug, {
        q: q || undefined,
        category: category || undefined,
        limit,
        offset,
      }),
  });

  const buyNowProductQuery = useQuery({
    queryKey: ["storefront", "public-product", slug, buyNowProductId],
    enabled: Boolean(slug && buyNowProductId),
    queryFn: () =>
      storefrontService.getPublicProductDetail(slug, buyNowProductId!),
  });

  useEffect(() => {
    if (!storefrontQuery.data) return;
    document.title =
      storefrontQuery.data.seo_title ||
      `${storefrontQuery.data.display_name} | Store`;
    setMetaDescription(
      storefrontQuery.data.seo_description || storefrontQuery.data.description,
    );
  }, [storefrontQuery.data]);

  useEffect(() => {
    if (!buyNowProductQuery.data?.variants.length) return;
    if (!selectedVariantId) {
      setSelectedVariantId(buyNowProductQuery.data.variants[0].id);
    }
  }, [buyNowProductQuery.data, selectedVariantId]);

  const selectedVariant = useMemo(
    () =>
      buyNowProductQuery.data?.variants.find(
        (variant) => variant.id === selectedVariantId,
      ) ?? null,
    [buyNowProductQuery.data, selectedVariantId],
  );

  const quickCheckoutMutation = useMutation({
    mutationFn: async () => {
      const variantId = selectedVariantId.trim();
      if (!buyNowProductId || !variantId) {
        throw new Error("Select a product variant to continue.");
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
        cancel_redirect_url: window.location.href,
      });
      const placed = await checkoutService.placePublicOrder(
        session.session_token,
        {
          payment_method: paymentMethod,
          note: note.trim() || undefined,
        },
      );
      return { session, placed };
    },
    onSuccess: ({ session, placed }) => {
      setCheckoutResult({
        paymentCheckoutUrl: session.payment_checkout_url,
        orderId: placed.order_id,
        orderStatus: placed.order_status,
        totalAmount: placed.total_amount,
      });
      showToast({
        title: "Checkout initiated",
        description: "Order created. Continue to payment to complete purchase.",
        variant: "success",
      });
    },
    onError: (error) => {
      showToast({
        title: "Could not start checkout",
        description: getApiErrorMessage(error),
        variant: "error",
      });
    },
  });

  const categories = useMemo(() => {
    if (!productsQuery.data) return [];
    return [
      ...new Set(
        productsQuery.data.items
          .map((item) => item.category)
          .filter(Boolean) as string[],
      ),
    ];
  }, [productsQuery.data]);

  if (storefrontQuery.isLoading || productsQuery.isLoading) {
    return <LoadingState label="Loading storefront..." />;
  }

  if (
    storefrontQuery.isError ||
    productsQuery.isError ||
    !storefrontQuery.data ||
    !productsQuery.data
  ) {
    return (
      <ErrorState
        message="Unable to load this storefront."
        onRetry={() => {
          storefrontQuery.refetch();
          productsQuery.refetch();
        }}
      />
    );
  }

  const storefront = storefrontQuery.data;
  const products = productsQuery.data;

  function openBuyNow(productId: string, productName: string) {
    setBuyNowProductId(productId);
    setBuyNowProductName(productName);
    setSelectedVariantId("");
    setQty(1);
    setPaymentMethod("transfer");
    setNote("");
    setCheckoutResult(null);
  }

  return (
    <div
      className="min-h-screen px-4 py-8 sm:px-8"
      style={{
        background: `radial-gradient(circle at 10% 20%, ${storefront.accent_color ?? "#16a34a"}22 0%, transparent 38%), radial-gradient(circle at 85% 12%, #1f2f4f22 0%, transparent 40%), linear-gradient(180deg, #f8fbff 0%, #eef4f8 100%)`,
      }}
    >
      <div className="mx-auto max-w-6xl space-y-6">
        <Card className="overflow-hidden border-0 bg-[linear-gradient(135deg,#132a42_0%,#1e3a57_45%,#243c54_100%)] text-white shadow-2xl">
          <div className="grid gap-4 md:grid-cols-[1.6fr_1fr]">
            <div className="space-y-3 p-6 sm:p-8">
              <p className="text-xs uppercase tracking-[0.28em] text-white/70">
                MoniDesk Storefront
              </p>
              <h1 className="font-heading text-3xl font-black sm:text-4xl">
                {storefront.display_name}
              </h1>
              {storefront.tagline ? (
                <p className="text-sm text-white/85">{storefront.tagline}</p>
              ) : null}
              {storefront.description ? (
                <p className="text-sm text-white/75">
                  {storefront.description}
                </p>
              ) : null}
            </div>
            <div className="bg-white/10 p-6 text-sm">
              <p className="text-xs uppercase tracking-wide text-white/70">
                Support
              </p>
              <p className="mt-2 font-semibold text-white">
                {storefront.support_email ?? "No support email"}
              </p>
              <p className="text-white/80">
                {storefront.support_phone ?? "No support phone"}
              </p>
              <div className="mt-4 space-y-2 text-xs text-white/75">
                {storefront.policy_shipping ? (
                  <p>Shipping: {storefront.policy_shipping}</p>
                ) : null}
                {storefront.policy_returns ? (
                  <p>Returns: {storefront.policy_returns}</p>
                ) : null}
              </div>
            </div>
          </div>
        </Card>

        <Card className="bg-white/90 backdrop-blur dark:bg-surface-900/85">
          <div className="grid gap-3 md:grid-cols-[2fr_1fr]">
            <Input
              label="Search Products"
              placeholder="Search by name or category..."
              value={q}
              onChange={(event) => setQ(event.target.value)}
            />
            <Select
              label="Category"
              value={category}
              onChange={(event) => setCategory(event.target.value)}
            >
              <option value="">All categories</option>
              {categories.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </Select>
          </div>
        </Card>

        {products.items.length === 0 ? (
          <Card>
            <EmptyState
              title="No products published yet"
              description="This store will display products once they are published."
            />
          </Card>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {products.items.map((product, index) => (
              <div
                key={product.id}
                className="animate-fade-up"
                style={{ animationDelay: `${index * 40}ms` }}
              >
                <Card>
                  <div className="h-full rounded-xl border border-surface-100 bg-white/95 p-5 transition duration-300 hover:-translate-y-0.5 hover:shadow-glow dark:border-surface-700 dark:bg-surface-900/85">
                    <p className="text-xs uppercase tracking-wide text-surface-500">
                      {product.category ?? "General"}
                    </p>
                    <h3 className="mt-2 font-heading text-xl font-bold text-surface-800">
                      {product.name}
                    </h3>
                    <p className="mt-2 text-sm text-surface-600">
                      {product.published_variant_count} variant
                      {product.published_variant_count === 1 ? "" : "s"}
                    </p>
                    <p className="mt-3 text-lg font-black text-surface-800">
                      {product.starting_price != null
                        ? `From ${formatCurrency(product.starting_price, profileQuery.data?.base_currency)}`
                        : "Price on request"}
                    </p>
                    <div className="mt-4 flex flex-wrap items-center gap-2">
                      <Link
                        to={`/store/${slug}/products/${product.id}`}
                        className="inline-flex h-9 items-center justify-center rounded-lg border border-surface-200 px-3 text-xs font-semibold uppercase tracking-wide text-cobalt-700 transition hover:bg-surface-50 dark:border-surface-600 dark:text-cobalt-200 dark:hover:bg-surface-700/30"
                      >
                        View Details
                      </Link>
                      <Button
                        type="button"
                        size="sm"
                        onClick={() => openBuyNow(product.id, product.name)}
                      >
                        Buy Now
                      </Button>
                    </div>
                  </div>
                </Card>
              </div>
            ))}
          </div>
        )}

        <Card className="bg-white/90 dark:bg-surface-900/85">
          <PaginationControls
            pagination={products.pagination}
            onPrev={() => setOffset(Math.max(0, offset - limit))}
            onNext={() => setOffset(offset + limit)}
          />
        </Card>
      </div>

      <Modal
        open={Boolean(buyNowProductId)}
        title={
          buyNowProductName ? `Buy ${buyNowProductName}` : "Quick Checkout"
        }
        onClose={() => setBuyNowProductId(null)}
      >
        {buyNowProductQuery.isLoading ? (
          <LoadingState label="Preparing checkout..." />
        ) : buyNowProductQuery.isError || !buyNowProductQuery.data ? (
          <ErrorState
            message="Unable to load product variants for checkout."
            onRetry={() => buyNowProductQuery.refetch()}
          />
        ) : buyNowProductQuery.data.variants.length === 0 ? (
          <EmptyState
            title="No variants available"
            description="This product has no published variants yet."
          />
        ) : (
          <div className="space-y-4">
            <Select
              label="Variant"
              value={selectedVariantId}
              onChange={(event) => setSelectedVariantId(event.target.value)}
            >
              {buyNowProductQuery.data.variants.map((variant) => (
                <option key={variant.id} value={variant.id}>
                  {variant.label ?? "Standard"} - {variant.size}
                  {variant.selling_price != null
                    ? ` (${formatCurrency(variant.selling_price, profileQuery.data?.base_currency)})`
                    : ""}
                </option>
              ))}
            </Select>
            <div className="grid gap-3 sm:grid-cols-2">
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
                onChange={(event) =>
                  setPaymentMethod(
                    event.target.value as "cash" | "transfer" | "pos",
                  )
                }
              >
                <option value="transfer">Transfer</option>
                <option value="pos">POS</option>
                <option value="cash">Cash</option>
              </Select>
            </div>
            <div className="rounded-lg border border-surface-100 bg-surface-50 p-3 text-sm">
              <p className="text-surface-500">Estimated Total</p>
              <p className="mt-1 text-lg font-black text-surface-800">
                {selectedVariant?.selling_price != null
                  ? formatCurrency(
                      selectedVariant.selling_price *
                        Math.max(1, Number(qty || 1)),
                      profileQuery.data?.base_currency,
                    )
                  : "Price unavailable"}
              </p>
            </div>
            <Textarea
              label="Order Note (optional)"
              rows={3}
              value={note}
              onChange={(event) => setNote(event.target.value)}
              placeholder="Special instructions or delivery notes..."
            />
            <div className="flex flex-wrap items-center gap-2">
              <Button
                type="button"
                loading={quickCheckoutMutation.isPending}
                onClick={() => quickCheckoutMutation.mutate()}
                disabled={
                  !selectedVariantId || selectedVariant?.selling_price == null
                }
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
              <div className="rounded-lg border border-mint-200 bg-mint-50 p-3 text-sm text-mint-800">
                <p className="font-semibold">Order created successfully</p>
                <p className="mt-1">Order ID: {checkoutResult.orderId}</p>
                <p>Order Status: {checkoutResult.orderStatus}</p>
                <p>
                  Total:{" "}
                  {formatCurrency(
                    checkoutResult.totalAmount,
                    profileQuery.data?.base_currency,
                  )}
                </p>
              </div>
            ) : null}
          </div>
        )}
      </Modal>
    </div>
  );
}
