import type { PaginationMeta } from "../../api/types";
import { Button } from "./button";

interface PaginationControlsProps {
  pagination: PaginationMeta;
  onPrev: () => void;
  onNext: () => void;
  onPageSizeChange?: (size: number) => void;
  pageSize?: number;
  pageSizeOptions?: number[];
}

export function PaginationControls({
  pagination,
  onPrev,
  onNext,
  onPageSizeChange,
  pageSize,
  pageSizeOptions = [10, 20, 50]
}: PaginationControlsProps) {
  const page = Math.floor(pagination.offset / pagination.limit) + 1;
  const totalPages = Math.max(1, Math.ceil(pagination.total / pagination.limit));

  return (
    <div className="mt-4 flex flex-col gap-3 rounded-xl border border-surface-100 bg-surface-50 p-3 text-sm sm:flex-row sm:items-center sm:justify-between">
      <p className="text-surface-600">
        Page {page} of {totalPages} ({pagination.total} total)
      </p>
      <div className="flex items-center gap-2">
        {onPageSizeChange ? (
          <label className="flex items-center gap-2 text-xs text-surface-500">
            Rows
            <select
              className="h-8 rounded border border-surface-200 bg-white px-2 text-xs"
              value={pageSize ?? pagination.limit}
              onChange={(event) => onPageSizeChange(Number(event.target.value))}
            >
              {pageSizeOptions.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </label>
        ) : null}
        <Button type="button" size="sm" variant="ghost" onClick={onPrev} disabled={pagination.offset <= 0}>
          Previous
        </Button>
        <Button type="button" size="sm" variant="ghost" onClick={onNext} disabled={!pagination.has_next}>
          Next
        </Button>
      </div>
    </div>
  );
}
