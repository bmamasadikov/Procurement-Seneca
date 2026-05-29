import type { Metadata, Viewport } from "next";
import "./globals.css";
import { Toaster } from "react-hot-toast";
import { Providers } from "@/components/Providers";
import { PwaRegistration } from "@/components/PwaRegistration";

export const metadata: Metadata = {
  title: "SENTASK — Seneca Task Manager",
  description: "Seneca internal task management system",
  applicationName: "SENTASK",
  manifest: "/manifest.webmanifest",
  icons: {
    icon: "/pwa/icon-192",
    apple: "/pwa/icon-192",
  },
  appleWebApp: {
    capable: true,
    title: "SENTASK",
    statusBarStyle: "default",
  },
  formatDetection: {
    telephone: false,
  },
};

export const viewport: Viewport = {
  themeColor: "#1e3a8a",
  colorScheme: "light",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body
        className="antialiased"
        style={{
          fontFamily:
            '"Inter", "Segoe UI", -apple-system, BlinkMacSystemFont, "Helvetica Neue", sans-serif',
        }}
      >
        <Providers>
          <PwaRegistration />
          {children}
          <Toaster
            position="top-right"
            toastOptions={{
              duration: 4000,
              style: {
                background: "#1e293b",
                color: "#f8fafc",
                borderRadius: "10px",
                fontSize: "14px",
              },
            }}
          />
        </Providers>
      </body>
    </html>
  );
}
