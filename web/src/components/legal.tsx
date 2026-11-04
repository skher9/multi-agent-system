/** The frame and text styles for the privacy and terms pages. */

import type { ReactNode } from "react";

import { SiteFooter, SiteNav } from "@/components/site";

export const CONTACT_EMAIL = "skher3318@gmail.com";

export function LegalPage({
  title,
  updated,
  children,
}: {
  title: string;
  updated: string;
  children: ReactNode;
}) {
  return (
    <>
      <SiteNav />
      <main className="mx-auto max-w-2xl px-4 py-12">
        <h1 className="text-3xl font-semibold tracking-tight">{title}</h1>
        <p className="mt-2 text-sm text-muted">Last updated {updated}</p>
        <div className="mt-10 space-y-10 text-[15px] leading-7 text-muted [&_a]:text-ink [&_a]:underline [&_a]:underline-offset-4 [&_li]:mt-2 [&_strong]:font-medium [&_strong]:text-ink [&_ul]:list-disc [&_ul]:pl-5">
          {children}
        </div>
      </main>
      <SiteFooter />
    </>
  );
}

export function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section>
      <h2 className="mb-3 text-lg font-medium text-ink">{title}</h2>
      <div className="space-y-3">{children}</div>
    </section>
  );
}
