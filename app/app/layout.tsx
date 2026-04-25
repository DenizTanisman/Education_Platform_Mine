import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "IAU AI Platform",
  description: "Yapay zekayı ünite ünite öğrenip pratik yapacağın platform.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}): React.ReactElement {
  return (
    <html lang="tr">
      <body>{children}</body>
    </html>
  );
}
