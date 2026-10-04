"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { usersService } from "@/services/users.service";

export function useActivateUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (userId: string) => usersService.activateUser(userId),
    onSuccess: (updatedUser) => {
      qc.setQueryData(["users", updatedUser.id], updatedUser);
      qc.invalidateQueries({ queryKey: ["users"] });
    },
  });
}
