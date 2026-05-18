"use client";
import { useSearchParams } from "next/navigation";
import { redirect } from "next/navigation";
import { Suspense } from "react";

function Redirector() {
  const params = useSearchParams();
  const token = params.get("token");
  redirect(token ? `/invite?token=${token}` : "/invite");
  return null; // redirect() throws — this satisfies TypeScript's ReactNode requirement
}

export default function OldInviteRedirect() {
  return (
    <Suspense>
      <Redirector />
    </Suspense>
  );
}
