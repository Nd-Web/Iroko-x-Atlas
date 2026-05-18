import axios from "axios";
import type { User, UserListResponse, UpdateUserRequest } from "@/lib/types";

const api = axios.create({ headers: { "Content-Type": "application/json" } });

api.interceptors.response.use(
  (res) => res,
  (err) => {
    const message =
      err.response?.data?.error ?? "Something went wrong. Please try again.";
    return Promise.reject(new Error(message));
  },
);

export const usersService = {
  listUsers: (): Promise<UserListResponse> =>
    api.get<UserListResponse>("/api/users").then((r) => r.data),

  getUser: (userId: string): Promise<User> =>
    api.get<User>(`/api/users/${userId}`).then((r) => r.data),

  updateUser: (userId: string, body: UpdateUserRequest): Promise<User> =>
    api.patch<User>(`/api/users/${userId}`, body).then((r) => r.data),

  deleteUser: (userId: string): Promise<null> =>
    api.delete(`/api/users/${userId}`).then(() => null),

  activateUser: (userId: string): Promise<User> =>
    api.post<User>(`/api/users/${userId}/activate`).then((r) => r.data),

  deactivateUser: (userId: string): Promise<User> =>
    api.post<User>(`/api/users/${userId}/deactivate`).then((r) => r.data),
};
