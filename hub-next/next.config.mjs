/** @type {import('next').NextConfig} */
const nextConfig = {
  // Standalone output produces a self-contained server bundle for a slim
  // Cloud Run container (no need to ship node_modules).
  output: 'standalone',
  // The dynamic company screens read Firestore at request time; nothing is
  // statically prerendered with stale data.
  // Keep the Firestore Admin SDK (native deps) external to the server bundle.
  serverExternalPackages: ['@google-cloud/firestore'],
};

export default nextConfig;
