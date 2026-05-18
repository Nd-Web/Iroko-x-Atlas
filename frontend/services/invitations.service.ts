import axios from "axios";
import type {
  InviteRequest,
  AcceptInviteRequest,
  InviteTokenPayload,
  InvitationsResponse,
  User,
} from "@/lib/types";

const api = axios.create({ headers: { "Content-Type": "application/json" } });

api.interceptors.response.use(
  (res) => res,
  (err) => {
    const message =
      err.response?.data?.error ?? "Something went wrong. Please try again.";
    return Promise.reject(new Error(message));
  },
);

export const invitationsService = {
  listInvitations: (): Promise<InvitationsResponse> =>
    api.get<InvitationsResponse>("/api/auth/invitations").then((r) => r.data),

  sendInvite: (body: InviteRequest): Promise<void> =>
    api.post("/api/auth/invite", body).then(() => undefined),

  validateToken: (token: string): Promise<InviteTokenPayload> =>
    api.get<InviteTokenPayload>(`/api/auth/invite/${token}`).then((r) => r.data),

  acceptInvite: (body: AcceptInviteRequest): Promise<{ user: User }> =>
    api.post<{ user: User }>("/api/auth/accept-invite", body).then((r) => r.data),

  revokeInvitation: (inviteId: string): Promise<null> =>
    api.delete(`/api/auth/invitations/${inviteId}`).then(() => null),
};
