"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { usersService } from "@/services/users.service";

export function useDeactivateUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (userId: string) => usersService.deactivateUser(userId),
    onSuccess: (updatedUser) => {
      qc.setQueryData(["users", updatedUser.id], updatedUser);
      qc.invalidateQueries({ queryKey: ["users"] });
    },
  });
}
