import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: 'standalone',

  // Performance optimizations
  experimental: {
    optimizePackageImports: ['lucide-react'],
  },

  // Compression
  compress: true,

  // Image optimization
  images: {
    formats: ['image/avif', 'image/webp'],
  },

  // Bundle analyzer (disabled by default)
  // webpack: (config) => { config.plugins.push(new BundleAnalyzerPlugin()); return config; }

  // Security headers (in addition to middleware)
  async headers() {
    return [
      {
        source: '/(.*)',
        headers: [
          { key: 'X-Content-Type-Options', value: 'nosniff' },
          { key: 'X-Frame-Options', value: 'DENY' },
          { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
        ],
      },
      {
        source: '/api/(.*)',
        headers: [
          { key: 'Cache-Control', value: 'no-store' },
        ],
      },
    ];
  },
};

export default nextConfig;
