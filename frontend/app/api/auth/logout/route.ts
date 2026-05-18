/**
 * app/api/auth/logout/route.ts
 *
 * Clears the httpOnly auth cookie, ending the user's session.
 * The client should call DELETE /api/auth/logout and then navigate to /login.
 *
 * There is no backend logout endpoint in AtlasCore, so this handler simply
 * removes the cookie from the browser — the JWT becomes effectively useless
 * once the cookie is deleted.
 */

import { cookies } from "next/headers";
import { COOKIE_NAME } from "@/lib/config";

export async function DELETE() {
  const cookieStore = await cookies();

  // Delete the auth cookie — this invalidates the session on the client side
  cookieStore.delete(COOKIE_NAME);

  return Response.json({ success: true }, { status: 200 });
}
