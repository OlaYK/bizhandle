import { LoadingState } from "./loading-state";

export function PageLoading() {
  return (
    <div className="p-4 sm:p-6">
      <LoadingState label="Loading page..." />
    </div>
  );
}
