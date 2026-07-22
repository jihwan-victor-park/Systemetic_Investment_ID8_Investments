/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  serverExternalPackages: ['@google-cloud/firestore', '@google-cloud/storage'],
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
