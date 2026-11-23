import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'ClipForge AI',
  description: 'AI-powered video clipping and publishing platform',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
