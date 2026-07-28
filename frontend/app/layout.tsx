import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "Feishu Project Weekly Agent",
  description: "Foundation application",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
