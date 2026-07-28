/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  serverExternalPackages: ['@google-cloud/firestore', '@google-cloud/storage'],
  // Everything under /_next/static already gets a long-lived immutable
  // Cache-Control header for free (Next.js content-hashes those filenames).
  // Files served straight out of /public -- the self-hosted Roboto Serif/
  // Sora .ttf files (globals.css's @font-face rules) and the navbar logo --
  // get none of that by default, so every single page load was re-requesting
  // ~650KB of font files from the server instead of the browser's own cache.
  // These never change without a filename change (there's no cache-busting
  // query param anywhere they're referenced), so "cache forever" is safe.
  async headers() {
    return [
      {
        source: '/fonts/:path*',
        headers: [{ key: 'Cache-Control', value: 'public, max-age=31536000, immutable' }],
      },
      {
        source: '/img/:path*',
        headers: [{ key: 'Cache-Control', value: 'public, max-age=31536000, immutable' }],
      },
    ];
  },
  async redirects() {
    return [
      {
        // Old URL for the fund overview page, renamed off /investors/research
        // -- keep redirecting in case it's already been shared with LPs.
        source: '/investors/research/fund-one-pager',
        destination: '/investors/materials/fund-overview',
        permanent: true,
      },
    ];
  },
};

export default nextConfig;
