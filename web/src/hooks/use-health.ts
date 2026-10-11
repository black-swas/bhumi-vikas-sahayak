import { useQuery } from "@tanstack/react-query";
import { api } from "#/api/client";

/** GET /api/health every 30 s: drives the mode badge and the amendment count in the banner. */
export function useHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: api.health,
    refetchInterval: 30_000,
    retry: false,
    staleTime: 15_000,
  });
}
