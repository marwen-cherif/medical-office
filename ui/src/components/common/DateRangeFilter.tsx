import { Input } from "@/components/ui/input";

/** Filtre de période : deux champs date natifs (ISO), bornes incluses. */
export function DateRangeFilter({
  from,
  to,
  onChange,
}: {
  from: string;
  to: string;
  onChange: (range: { from: string; to: string }) => void;
}) {
  return (
    <div className="flex items-center gap-2">
      <Input
        type="date"
        className="w-40"
        value={from}
        onChange={(e) => onChange({ from: e.target.value, to })}
        aria-label="Du"
      />
      <span className="text-sm text-muted">au</span>
      <Input
        type="date"
        className="w-40"
        value={to}
        onChange={(e) => onChange({ from, to: e.target.value })}
        aria-label="Au"
      />
    </div>
  );
}
