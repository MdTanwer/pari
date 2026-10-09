import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'PARI — a coding agent in your terminal',
  description:
    'PARI reads a repository, edits files, and runs shell commands. On Linux, commands stay inside Bubblewrap. Sign in with DeepSeek, OpenAI, Anthropic, Grok, or OpenRouter.',
  keywords: [
    'pari',
    'pari-cli',
    'terminal coding agent',
    'ai coding assistant',
    'developer tools',
  ],
  authors: [{ name: 'PARI contributors' }],
  metadataBase: new URL('https://pari-cli.in'),
  openGraph: {
    title: 'PARI — a coding agent in your terminal',
    description:
      'Search the repo, apply an exact edit, and run commands in a Linux Bubblewrap sandbox.',
    url: 'https://pari-cli.in',
    siteName: 'PARI',
    type: 'website',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'PARI — a coding agent in your terminal',
    description:
      'Search the repo, apply an exact edit, and run commands in a Linux Bubblewrap sandbox.',
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
