import { redirect } from "next/navigation";
export default function OldForgotPasswordRedirect() {
  redirect("/forgot-password");
}
