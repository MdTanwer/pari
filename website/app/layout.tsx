import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'PARI — Terminal Coding Agent | Exact, Kernel-Sandboxed, Zero-Token-Burn',
  description:
    'A synthesis architecture engineered for terminal coding agents. Features 11-layer runtime topology, multi-platform kernel isolation, and differential TUI rendering.',
  keywords: [
    'pari',
    'pari-cli',
    'terminal coding agent',
    'ai coding assistant',
    'claude code',
    'openai codex',
    'developer tools',
  ],
  authors: [{ name: 'Md Tanwer & PARI Contributors' }],
  metadataBase: new URL('https://pari-cli.in'),
  openGraph: {
    title: 'PARI — Next-Generation Terminal Coding Agent',
    description:
      'Engineered for 50%+ benchmark pass rates. Closes the six fatal systems failure modes in production AI agents.',
    url: 'https://pari-cli.in',
    siteName: 'PARI',
    type: 'website',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'PARI — Terminal Coding Agent',
    description: 'Kernel-sandboxed, exact diff edits, durable Merkle DAG sessions.',
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
