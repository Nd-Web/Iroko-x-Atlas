import { apiRequest } from "@/lib/api-client";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const redirectUri = searchParams.get("redirect_uri");
  const connectorType = searchParams.get("connector_type") ?? "onedrive";
  const instanceUrl = searchParams.get("instance_url");

  if (!redirectUri) {
    return Response.json({ error: "redirect_uri is required" }, { status: 400 });
  }

  const query = new URLSearchParams({
    redirect_uri: redirectUri,
    connector_type: connectorType,
  });
  if (instanceUrl) query.set("instance_url", instanceUrl);

  const { data, error, status } = await apiRequest(
    `/api/connectors/auth-url?${query.toString()}`
  );

  if (error) {
    return Response.json({ error }, { status: status || 500 });
  }

  return Response.json(data, { status: 200 });
}
