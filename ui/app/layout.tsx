import type { Metadata } from "next";
import "@salt-ds/theme/index.css";
import "./globals.css";
import { AppProviders } from "./providers";

export const metadata: Metadata = {
  title: "FilingScope",
  description: "SEC financial-intelligence and accounting-quality research workspace",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <AppProviders>{children}</AppProviders>
      </body>
    </html>
  );
}
