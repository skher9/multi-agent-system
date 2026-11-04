import type { NextConfig } from "next";

const isDev = process.env.NODE_ENV === "development";

// The browser talks to our Python API and to Pusher (live run events), nothing else.
const apiOrigin = process.env.NEXT_PUBLIC_API_URL
  ? new URL(process.env.NEXT_PUBLIC_API_URL).origin
  : "http://localhost:8000";
const pusherCluster = process.env.NEXT_PUBLIC_PUSHER_CLUSTER;
const pusherHosts = pusherCluster
  ? `wss://ws-${pusherCluster}.pusher.com https://sockjs-${pusherCluster}.pusher.com`
  : "";

// Content Security Policy: which sources the browser may load from. Pages, scripts and
// fonts are same-origin (next/font self-hosts fonts). Scripts keep 'unsafe-inline' because
// nonces need every page rendered per request, which rules out Partial Prerendering
// (Next.js CSP guide, "Without Nonces"). React escapes rendered text, and we never use
// dangerouslySetInnerHTML, so inline-script injection has no way in.
const csp = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline'${isDev ? " 'unsafe-eval'" : ""}`,
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' blob: data:",
  "font-src 'self'",
  `connect-src 'self' ${apiOrigin} ${pusherHosts}`.trim(),
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'", // no one may put our pages in a frame (clickjacking)
  "upgrade-insecure-requests",
].join("; ");

const securityHeaders = [
  { key: "Content-Security-Policy", value: csp },
  // HTTPS only, for two years, subdomains included
  { key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains; preload" },
  { key: "X-Frame-Options", value: "DENY" }, // older browsers' frame-ancestors
  { key: "X-Content-Type-Options", value: "nosniff" }, // don't guess file types
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), browsing-topics=()" },
];

const nextConfig: NextConfig = {
  /* config options here */
  cacheComponents: true,
  partialPrefetching: true,
  poweredByHeader: false, // don't advertise the framework
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  async headers() {
    return [{ source: "/(.*)", headers: securityHeaders }];
  },
};

export default nextConfig;
