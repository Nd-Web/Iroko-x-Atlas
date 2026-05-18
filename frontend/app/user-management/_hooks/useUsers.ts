"use client";

import { useQuery } from "@tanstack/react-query";
import { usersService } from "@/services/users.service";

export function useUsers() {
  return useQuery({
    queryKey: ["users"],
    queryFn: usersService.listUsers,
    staleTime: 0,
    refetchOnWindowFocus: true,
  });
}
