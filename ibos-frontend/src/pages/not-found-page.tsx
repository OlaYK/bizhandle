import { Link } from "react-router-dom";
import { Button } from "../components/ui/button";

export function NotFoundPage() {
  return (
    <div className="flex min-h-[70vh] flex-col items-center justify-center gap-4 text-center">
      <p className="text-xs uppercase tracking-wide text-surface-500">404</p>
      <h1 className="font-heading text-3xl font-black text-surface-800">Page not found</h1>
      <p className="text-sm text-surface-500">The page you requested does not exist.</p>
      <Link to="/">
        <Button>Go to Dashboard</Button>
      </Link>
    </div>
  );
}
