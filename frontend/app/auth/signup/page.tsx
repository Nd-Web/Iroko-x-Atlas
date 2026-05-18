// Signup page: org creation + first-user registration flow
import { redirect } from "next/navigation";

/**
 * Signup is not yet enabled — redirect to login.
 * Replace this with a full registration form when ready.
 */
export default function SignupPage() {
  redirect("/login");
}