/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  serverExternalPackages: ['@google-cloud/firestore'],
};

export default nextConfig;
