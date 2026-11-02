import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "NLTI — Provincial Construction Intelligence",
  description:
    "Source-attributed public procurement information for Newfoundland and Labrador construction.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
