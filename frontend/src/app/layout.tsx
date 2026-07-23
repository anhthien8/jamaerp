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
  // PWA tối thiểu (spec 08 §1.4): nhân viên "Thêm vào màn hình chính" mở như app.
  // Lưu ý: cần bổ sung file icon-192.png + icon-512.png vào /public (logo JAMA).
  manifest: "/manifest.json",
  appleWebApp: { capable: true, statusBarStyle: "black-translucent", title: "JAMA" },
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
