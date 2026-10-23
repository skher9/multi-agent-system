"use client";

import Pusher from "pusher-js";
import { useEffect, useState } from "react";

import { api } from "@/lib/api/client";

// Must match TEST_CHANNEL / TEST_EVENT in backend/api/routes/realtime.py
const CHANNEL = "setup-test";
const EVENT = "ping";

const key = process.env.NEXT_PUBLIC_PUSHER_KEY;
const cluster = process.env.NEXT_PUBLIC_PUSHER_CLUSTER;

export function LiveEvents() {
  const [received, setReceived] = useState<string[]>([]);
  const [sendError, setSendError] = useState<string | null>(null);

  useEffect(() => {
    if (!key || !cluster) return;
    // The browser connects to Pusher directly (public key only, never the secret).
    const pusher = new Pusher(key, { cluster });
    pusher.subscribe(CHANNEL).bind(EVENT, (data: { sent_at: string }) => {
      setReceived((prev) => [`received event sent at ${data.sent_at}`, ...prev]);
    });
    return () => {
      pusher.unsubscribe(CHANNEL);
      pusher.disconnect();
    };
  }, []);

  async function send() {
    setSendError(null);
    try {
      const { error } = await api.POST("/realtime/test");
      if (error) setSendError("Backend could not send the event. Are the Pusher keys set?");
    } catch {
      setSendError("Can't reach the API. Is the backend running?");
    }
  }

  if (!key || !cluster) {
    return (
      <p className="text-amber-700">
        Set NEXT_PUBLIC_PUSHER_KEY and NEXT_PUBLIC_PUSHER_CLUSTER in web/.env.local.
      </p>
    );
  }

  return (
    <section className="space-y-4">
      <button type="button" onClick={send} className="rounded border px-3 py-1 text-sm">
        Send test event
      </button>
      {sendError && <p className="text-red-700">{sendError}</p>}
      <ul className="space-y-1 font-mono text-sm">
        {received.length === 0 && <li className="text-gray-500">Waiting for events…</li>}
        {received.map((line) => (
          <li key={line}>{line}</li>
        ))}
      </ul>
    </section>
  );
}
