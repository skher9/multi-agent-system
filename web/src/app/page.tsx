import Link from "next/link";

export default function Home() {
  return (
    <main className="mx-auto max-w-2xl space-y-4 p-8">
      <h1 className="text-2xl font-semibold">Multi-Agent System</h1>
      <p className="text-gray-600">Setup phase. Developer pages:</p>
      <ul className="list-disc pl-6">
        <li>
          <Link href="/status" className="underline">
            Service status
          </Link>
        </li>
        <li>
          <Link href="/realtime-test" className="underline">
            Realtime test
          </Link>
        </li>
      </ul>
    </main>
  );
}
