import { LiveEvents } from "./live-events";

export const metadata = { title: "Realtime test" };

export default function RealtimeTestPage() {
  return (
    <main className="mx-auto max-w-2xl space-y-6 p-8">
      <h1 className="text-2xl font-semibold">Realtime test</h1>
      <p className="text-sm text-gray-600">
        The button asks the backend to send a Pusher event. If it appears below, the path backend →
        Pusher → browser works.
      </p>
      <LiveEvents />
    </main>
  );
}
