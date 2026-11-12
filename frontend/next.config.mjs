const api = new URL(process.env.API_INTERNAL_URL || "http://127.0.0.1:8000");
if (!["http:", "https:"].includes(api.protocol) || api.username || api.password)
  throw new Error("API_INTERNAL_URL inválida");
export default {
  distDir: process.env.ALZACE_FRONTEND_DIST || ".next",
  poweredByHeader: false,
  devIndicators: false,
  async rewrites() {
    return [{ source: "/api/:path*", destination: api.origin + "/api/:path*" }];
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "same-origin" },
          { key: "X-Frame-Options", value: "DENY" },
          {
            key: "Content-Security-Policy",
            value:
              "default-src 'none'; frame-ancestors 'none'; object-src 'none'; base-uri 'none'; form-action 'none'",
          },
          {
            key: "Permissions-Policy",
            value: "camera=(), microphone=(), geolocation=()",
          },
        ],
      },
    ];
  },
};
