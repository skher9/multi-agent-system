import type { Metadata } from "next";

import { AuthForm } from "@/components/auth-form";
import { enabledProviders } from "@/lib/auth";

export const metadata: Metadata = { title: "Sign up" };

export default function SignUpPage() {
  return <AuthForm mode="signup" providers={enabledProviders()} />;
}
