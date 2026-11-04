import type { Metadata } from "next";
import Link from "next/link";

import { CONTACT_EMAIL, LegalPage, Section } from "@/components/legal";

export const metadata: Metadata = {
  title: "Privacy",
  description: "What Agent Dev Team stores about you, who processes it, and how to delete it.",
};

export default function PrivacyPage() {
  return (
    <LegalPage title="Privacy policy" updated="4 November 2026">
      <p>
        Agent Dev Team is a portfolio project by Shravani Kher. This page says plainly what it
        stores about you, why, and how to remove it.
      </p>

      <Section title="What we store">
        <ul>
          <li>
            <strong>Your account:</strong> name, email address, whether the email is confirmed, and
            your profile picture link if you log in with Google or GitHub.
          </li>
          <li>
            <strong>Your password,</strong> only as a one-way hash (scrypt). Nobody can read the
            original, including us.
          </li>
          <li>
            <strong>Sessions:</strong> when you logged in, your IP address and browser name. Used to
            keep you logged in and to spot abuse.
          </li>
          <li>
            <strong>Google or GitHub login:</strong> the account link and tokens the provider
            issues. We ask only for your basic profile and email.
          </li>
          <li>
            <strong>Runs you start:</strong> the ticket text you write, what the agents did, the
            code they produced, and what it cost.
          </li>
          <li>
            <strong>Login attempts,</strong> counted for a short time per IP address, to slow down
            password guessing.
          </li>
        </ul>
      </Section>

      <Section title="What we don't do">
        <ul>
          <li>No ads, no tracking scripts, no analytics cookies.</li>
          <li>We never sell or share your data for marketing.</li>
          <li>
            The only cookies are the ones that keep you logged in. They are HTTP-only, so scripts on
            the page can&apos;t read them.
          </li>
        </ul>
      </Section>

      <Section title="Who processes it">
        <p>These services run parts of the site and only see what they need:</p>
        <ul>
          <li>
            <strong>Vercel:</strong> hosts the website.
          </li>
          <li>
            <strong>Neon:</strong> the Postgres database, in the United States (AWS us-east-2).
          </li>
          <li>
            <strong>Google and GitHub:</strong> only if you log in with them.
          </li>
          <li>
            <strong>Gmail:</strong> sends confirmation and password reset emails.
          </li>
          <li>
            <strong>OpenRouter</strong> and the AI model providers it routes to: receive your ticket
            text and the playground code, to plan and write the change.
          </li>
          <li>
            <strong>GitHub:</strong> stores the code changes the agents make, in a private
            playground repository.
          </li>
          <li>
            <strong>Pusher:</strong> carries live run updates to your browser.
          </li>
        </ul>
        <p>
          Because ticket text goes to AI models,{" "}
          <strong>don&apos;t put passwords, keys or personal details in a ticket.</strong>
        </p>
      </Section>

      <Section title="Deleting your data">
        <p>
          Go to <Link href="/settings">Settings</Link> and choose <strong>Delete account</strong>.
          It removes your account, logins and sessions at once. To have anything else removed, email{" "}
          <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a> and it will be done within 30
          days.
        </p>
      </Section>

      <Section title="Security">
        <p>
          All traffic uses HTTPS. Agent code runs in a throwaway sandbox that has none of our keys
          and can reach nothing on the internet except the npm package registry.
        </p>
      </Section>

      <Section title="Questions">
        <p>
          Email <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>. If this policy changes, the
          date at the top changes too.
        </p>
      </Section>
    </LegalPage>
  );
}
