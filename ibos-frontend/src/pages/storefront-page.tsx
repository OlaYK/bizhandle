import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { storefrontService } from "../api/services";
import { Card } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { Select } from "../components/ui/select";
import { PaginationControls } from "../components/ui/pagination-controls";
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

export function StorefrontPage() {
  const params = useParams();
  const slug = params.slug ?? "";
  const [q, setQ] = useState("");
  const [category, setCategory] = useState("");
  const [offset, setOffset] = useState(0);
  const limit = 24;

  useEffect(() => {
    setOffset(0);
  }, [q, category, slug]);

  const storefrontQuery = useQuery({
    queryKey: ["storefront", "public", slug],
    enabled: Boolean(slug),
    queryFn: () => storefrontService.getPublicStorefront(slug)
  });

  const productsQuery = useQuery({
    queryKey: ["storefront", "public-products", slug, q, category, limit, offset],
    enabled: Boolean(slug),
    queryFn: () =>
      storefrontService.listPublicProducts(slug, {
        q: q || undefined,
        category: category || undefined,
        limit,
        offset
      })
  });

  useEffect(() => {
    if (!storefrontQuery.data) return;
    document.title = storefrontQuery.data.seo_title || `${storefrontQuery.data.display_name} | Store`;
    setMetaDescription(storefrontQuery.data.seo_description || storefrontQuery.data.description);
  }, [storefrontQuery.data]);

  const categories = useMemo(() => {
    if (!productsQuery.data) return [];
    return [...new Set(productsQuery.data.items.map((item) => item.category).filter(Boolean) as string[])];
  }, [productsQuery.data]);

  if (storefrontQuery.isLoading || productsQuery.isLoading) {
    return <LoadingState label="Loading storefront..." />;
  }

  if (storefrontQuery.isError || productsQuery.isError || !storefrontQuery.data || !productsQuery.data) {
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

  return (
    <div
      className="min-h-screen px-4 py-8 sm:px-8"
      style={{
        background: `radial-gradient(circle at 10% 20%, ${storefront.accent_color ?? "#16a34a"}22 0%, transparent 38%), radial-gradient(circle at 85% 12%, #1f2f4f22 0%, transparent 40%), linear-gradient(180deg, #f8fbff 0%, #eef4f8 100%)`
      }}
    >
      <div className="mx-auto max-w-6xl space-y-6">
        <Card className="overflow-hidden border-0 bg-[linear-gradient(135deg,#132a42_0%,#1e3a57_45%,#243c54_100%)] text-white shadow-2xl">
          <div className="grid gap-4 md:grid-cols-[1.6fr_1fr]">
            <div className="space-y-3 p-6 sm:p-8">
              <p className="text-xs uppercase tracking-[0.28em] text-white/70">MoniDesk Storefront</p>
              <h1 className="font-heading text-3xl font-black sm:text-4xl">{storefront.display_name}</h1>
              {storefront.tagline ? <p className="text-sm text-white/85">{storefront.tagline}</p> : null}
              {storefront.description ? <p className="text-sm text-white/75">{storefront.description}</p> : null}
            </div>
            <div className="bg-white/10 p-6 text-sm">
              <p className="text-xs uppercase tracking-wide text-white/70">Support</p>
              <p className="mt-2 font-semibold text-white">{storefront.support_email ?? "No support email"}</p>
              <p className="text-white/80">{storefront.support_phone ?? "No support phone"}</p>
              <div className="mt-4 space-y-2 text-xs text-white/75">
                {storefront.policy_shipping ? <p>Shipping: {storefront.policy_shipping}</p> : null}
                {storefront.policy_returns ? <p>Returns: {storefront.policy_returns}</p> : null}
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
            <EmptyState title="No products published yet" description="This store will display products once they are published." />
          </Card>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {products.items.map((product, index) => (
              <Link
                key={product.id}
                to={`/store/${slug}/products/${product.id}`}
                className="animate-fade-up"
                style={{ animationDelay: `${index * 40}ms` }}
              >
                <Card className="h-full border border-surface-100 bg-white/95 transition duration-300 hover:-translate-y-0.5 hover:shadow-glow dark:border-surface-700 dark:bg-surface-900/85">
                  <p className="text-xs uppercase tracking-wide text-surface-500">{product.category ?? "General"}</p>
                  <h3 className="mt-2 font-heading text-xl font-bold text-surface-800">{product.name}</h3>
                  <p className="mt-2 text-sm text-surface-600">
                    {product.published_variant_count} variant
                    {product.published_variant_count === 1 ? "" : "s"}
                  </p>
                  <p className="mt-3 text-lg font-black text-surface-800">
                    {product.starting_price != null ? `From ${formatCurrency(product.starting_price)}` : "Price on request"}
                  </p>
                  <p className="mt-4 text-xs font-semibold uppercase tracking-wide text-cobalt-700 dark:text-cobalt-200">
                    View Details
                  </p>
                </Card>
              </Link>
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
    </div>
  );
}
