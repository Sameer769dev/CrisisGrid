/** @type {import("next").NextConfig} */
const PROD_RENDER_URL = "https://crisisgrid-api-m0dp.onrender.com";

function normalizeBackendUrl(raw) {
  let cleaned = (raw || "").trim().replace(/\/+$/, "");
  cleaned = cleaned.replace(/\/health$/i, "");
  if (!cleaned) return PROD_RENDER_URL;
  if (!/^https?:\/\//i.test(cleaned)) {
    const isLocal = /^(localhost|127\.0\.0\.1)(:\d+)?$/i.test(cleaned);
    cleaned = `${isLocal ? "http" : "https"}://${cleaned}`;
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
