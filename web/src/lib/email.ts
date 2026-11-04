/**
 * Sends email from a Gmail account over SMTP, with a Google "app password" (free).
 * Used for password reset links. Without GMAIL_USER and GMAIL_APP_PASSWORD (local dev),
 * it logs that it skipped instead of sending; the link itself is never logged.
 */
import nodemailer from "nodemailer";

const user = process.env.GMAIL_USER;
const pass = process.env.GMAIL_APP_PASSWORD;

const transport =
  user && pass ? nodemailer.createTransport({ service: "gmail", auth: { user, pass } }) : null;

export async function sendEmail(message: {
  to: string;
  subject: string;
  text: string;
  html: string;
}): Promise<void> {
  if (!transport) {
    console.warn("Email not sent: GMAIL_USER / GMAIL_APP_PASSWORD are not set.");
    return;
  }
  try {
    await transport.sendMail({ from: `Agent Dev Team <${user}>`, ...message });
  } catch (error) {
    console.error("Email failed to send:", error instanceof Error ? error.message : error);
  }
}
