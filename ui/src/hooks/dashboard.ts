import { useQuery } from "@tanstack/react-query";
import { client, unwrap } from "@/lib/api";

export function useDashboard(from: string, to: string) {
  return useQuery({
    queryKey: ["dashboard", from, to],
    queryFn: async () =>
      unwrap(
        await client.GET("/api/dashboard", {
          params: { query: { date_from: from, date_to: to } },
        }),
      ),
  });
}
