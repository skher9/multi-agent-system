import type { Metadata } from "next";
import { Bricolage_Grotesque, DM_Mono, Figtree } from "next/font/google";
import "./globals.css";

import { Backdrop } from "@/components/ui/backdrop";

const sans = Figtree({ subsets: ["latin"], variable: "--font-figtree" });
const display = Bricolage_Grotesque({
  subsets: ["latin"],
  weight: ["500", "700"],
  variable: "--font-bricolage",
});
const mono = DM_Mono({ subsets: ["latin"], weight: ["400", "500"], variable: "--font-dm-mono" });

export const metadata: Metadata = {
  title: { default: "Agent Dev Team", template: "%s · Agent Dev Team" },
  description: "An AI dev team that turns Jira tickets into tested, reviewed GitHub PRs.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${sans.variable} ${display.variable} ${mono.variable}`}>
      <body className="flex min-h-dvh flex-col font-sans">
        <Backdrop />
        {children}
      </body>
    </html>
  );
}
