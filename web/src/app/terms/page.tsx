import type { Metadata } from "next";
import Link from "next/link";

import { CONTACT_EMAIL, LegalPage, Section } from "@/components/legal";

export const metadata: Metadata = {
  title: "Terms",
  description: "The rules for using Agent Dev Team.",
};

export default function TermsPage() {
  return (
    <LegalPage title="Terms of use" updated="4 November 2026">
      <p>
        Agent Dev Team is a portfolio project by Shravani Kher, offered free so people can see how
        it works. By creating an account you agree to these terms.
      </p>

      <Section title="What the service is">
        <p>
          AI agents read a ticket, plan the work, write code in a playground repository, test it and
          open a pull request. It is a demonstration, not a commercial product, and it can change or
          go offline at any time.
        </p>
      </Section>

      <Section title="Fair use">
        <ul>
          <li>
            Don&apos;t try to break into the site, the sandbox or other people&apos;s accounts.
          </li>
          <li>
            Don&apos;t write tickets that ask for malware, attacks on other systems, or anything
            illegal.
          </li>
          <li>Don&apos;t automate sign-ups or runs, or overload the service.</li>
          <li>
            Don&apos;t put passwords, keys or personal details in tickets: they are sent to AI
            models.
          </li>
        </ul>
        <p>Accounts that break these rules may be removed.</p>
      </Section>

      <Section title="The code the agents write">
        <p>
          It is produced by AI and may contain mistakes. It lives in a playground repository and is
          never merged or run anywhere outside the sandbox without a person reviewing it. Review any
          code yourself before using it.
        </p>
      </Section>

      <Section title="No warranty">
        <p>
          The service is provided as is, with no guarantee that it is available, correct or fit for
          any purpose. As far as the law allows, Shravani Kher is not liable for any loss from using
          it.
        </p>
      </Section>

      <Section title="Your data">
        <p>
          The <Link href="/privacy">privacy policy</Link> explains what is stored and how to delete
          it. You can delete your account at any time from <Link href="/settings">Settings</Link>.
        </p>
      </Section>

      <Section title="Contact">
        <p>
          Questions or problems: <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>.
        </p>
      </Section>
    </LegalPage>
  );
}
