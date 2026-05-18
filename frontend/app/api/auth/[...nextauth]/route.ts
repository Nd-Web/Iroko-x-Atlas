// NextAuth.js catch-all: Azure AD provider, JWT + session callbacks
// Auth is handled by the custom /api/auth/login route — NextAuth not in use.
import { NextResponse } from "next/server";

export async function GET() {
  return NextResponse.json({ error: "Not implemented" }, { status: 404 });
}

export async function POST() {
  return NextResponse.json({ error: "Not implemented" }, { status: 404 });
}