import type { Metadata } from "next";

import { AuthForm } from "@/components/auth-form";
import { enabledProviders } from "@/lib/auth";

export const metadata: Metadata = { title: "Log in" };

export default function LoginPage() {
  return <AuthForm mode="login" providers={enabledProviders()} />;
}
