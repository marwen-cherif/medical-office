import { ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";

export const PAGE_SIZE = 20;

export function Pagination({
  total,
  page,
  pageSize = PAGE_SIZE,
  onPage,
}: {
  total: number;
  page: number;
  pageSize?: number;
  onPage: (p: number) => void;
}) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  if (total === 0) return null;
  const from = page * pageSize + 1;
  const to = Math.min(total, (page + 1) * pageSize);
  return (
    <div className="flex items-center justify-between text-sm text-muted">
      <span>
        {from}–{to} sur {total}
      </span>
      <div className="flex items-center gap-2">
        <Button
          variant="secondary"
          size="icon"
          disabled={page <= 0}
          onClick={() => onPage(page - 1)}
          aria-label="Page précédente"
        >
          <ChevronLeft className="size-4" />
        </Button>
        <span className="tabular-nums">
          {page + 1} / {pages}
        </span>
        <Button
          variant="secondary"
          size="icon"
          disabled={page + 1 >= pages}
          onClick={() => onPage(page + 1)}
          aria-label="Page suivante"
        >
          <ChevronRight className="size-4" />
        </Button>
      </div>
    </div>
  );
}
