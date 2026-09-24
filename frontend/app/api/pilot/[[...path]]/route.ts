import { makeProxyHandlers } from "@/lib/proxy";

export const { GET, POST } = makeProxyHandlers("/api/pilot");
