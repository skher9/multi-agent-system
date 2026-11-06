import { StatusBoard } from "./status-board";

export const metadata = { title: "Service status" };

export default function StatusPage() {
  return (
    <main className="mx-auto max-w-2xl space-y-6 p-8">
      <h1 className="font-display text-5xl leading-tight">Service status</h1>
      <p className="text-sm text-gray-600">
        Live result of <code>GET /health</code>: one row per external service.
      </p>
      <StatusBoard />
    </main>
  );
}
