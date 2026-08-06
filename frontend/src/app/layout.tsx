import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "@/lib/auth";
import { ToastProvider } from "@/components/ui/Toast";
import ErrorBoundary from "@/components/ui/ErrorBoundary";
import InstallBanner from "@/components/ui/InstallBanner";

const inter = Inter({
  subsets: ["latin", "vietnamese"],
  variable: "--font-inter",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  weight: ["400", "500"],
});

export const metadata: Metadata = {
  title: "JAMA HOME ERP — Hệ thống Quản lý",
  description: "ERP + CRM cho JAMA HOME — Nội thất cao cấp",
  // PWA (spec 08 §1.4): icon mark JM thương hiệu (sinh từ public/jama-logo.png,
  // xem lịch sử 22/07) — bộ icon-192/512 + maskable + apple-touch-icon.
  manifest: "/manifest.json",
  icons: {
    icon: [
      { url: "/icon-192.png", sizes: "192x192", type: "image/png" },
      { url: "/icon-512.png", sizes: "512x512", type: "image/png" },
    ],
    apple: "/apple-touch-icon.png",
  },
  appleWebApp: { capable: true, statusBarStyle: "black-translucent", title: "JAMA HOME" },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="vi" className="dark">
      <body className={`${inter.variable} ${jetbrainsMono.variable} font-sans antialiased`}>
        <ErrorBoundary>
          <AuthProvider>
            <ToastProvider>{children}</ToastProvider>
            <InstallBanner />
          </AuthProvider>
        </ErrorBoundary>
      </body>
    </html>
  );
}
