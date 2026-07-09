/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  serverExternalPackages: ['@google-cloud/firestore', '@google-cloud/storage'],
};

export default nextConfig;
