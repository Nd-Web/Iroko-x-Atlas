"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { usersService } from "@/services/users.service";
import type { UpdateUserRequest } from "@/lib/types";

export function useUpdateUser(userId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: UpdateUserRequest) => usersService.updateUser(userId, body),
    onSuccess: (updatedUser) => {
      qc.setQueryData(["users", userId], updatedUser);
      qc.invalidateQueries({ queryKey: ["users"] });
    },
  });
}
