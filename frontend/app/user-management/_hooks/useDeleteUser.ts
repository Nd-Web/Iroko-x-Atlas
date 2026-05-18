"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { usersService } from "@/services/users.service";

export function useDeleteUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (userId: string) => usersService.deleteUser(userId),
    onSuccess: (_, userId) => {
      qc.removeQueries({ queryKey: ["users", userId] });
      qc.invalidateQueries({ queryKey: ["users"] });
    },
  });
}
