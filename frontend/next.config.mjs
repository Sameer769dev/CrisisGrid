/** @type {import("next").NextConfig} */
const PROD_MODAL_URL = "https://baralsamir941--crisisgrid-api-crisisgrid-asgi.us-east.modal.run";

function normalizeBackendUrl(raw) {
  let cleaned = (raw || "").trim().replace(/\/+$/, "");
  cleaned = cleaned.replace(/\/health$/i, "");
  if (!cleaned) return PROD_MODAL_URL;
  if (!/^https?:\/\//i.test(cleaned)) {
    const isLocal = /^(localhost|127\.0\.0\.1)(:\d+)?$/i.test(cleaned);
    cleaned = `${isLocal ? "http" : "https"}://${cleaned}`;
  }
  const isLocalUrl = /^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/i.test(cleaned);
  if (!isLocalUrl && !/\.modal\.run$/i.test(cleaned)) {
    return PROD_MODAL_URL;
  }
  return cleaned;
}

const backendOrigin = normalizeBackendUrl(
  process.env.NEXT_PUBLIC_BACKEND_URL || process.env.NEXT_PUBLIC_API_BASE_URL
);

const nextConfig = {
  async rewrites() {
    return [
      {
        source: "/cg-api/:path*",
        destination: `${backendOrigin}/:path*`,
      },
    ];
  },
};

export default nextConfig;
