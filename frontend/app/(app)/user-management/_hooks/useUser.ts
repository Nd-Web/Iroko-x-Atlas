"use client";

import { useQuery } from "@tanstack/react-query";
import { usersService } from "@/services/users.service";

export function useUser(userId: string) {
  return useQuery({
    queryKey: ["users", userId],
    queryFn: () => usersService.getUser(userId),
    enabled: Boolean(userId),
    staleTime: 0,
    refetchOnWindowFocus: true,
  });
}
