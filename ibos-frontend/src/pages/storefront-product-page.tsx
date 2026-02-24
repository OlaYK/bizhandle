import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { storefrontService } from "../api/services";
import { Card } from "../components/ui/card";
import { LoadingState } from "../components/state/loading-state";
import { ErrorState } from "../components/state/error-state";
import { EmptyState } from "../components/state/empty-state";
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
  const slug = params.slug ?? "";
  const productId = params.productId ?? "";

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

        <Card className="bg-surface-900 text-surface-100">
          <h3 className="font-heading text-lg font-bold">Need to place an order?</h3>
          <p className="mt-2 text-sm text-surface-200">
            Contact {storefront.display_name} directly for checkout while online payment flow is being finalized.
          </p>
          <div className="mt-3 space-y-1 text-sm">
            <p>Email: {storefront.support_email ?? "Not provided"}</p>
            <p>Phone: {storefront.support_phone ?? "Not provided"}</p>
          </div>
        </Card>
      </div>
    </div>
  );
}
