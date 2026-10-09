import { readFileSync } from 'fs';
import { join } from 'path';
import { NextResponse } from 'next/server';

export function GET() {
  const html = readFileSync(
    join(process.cwd(), 'app/pari-cli-landing-page.html'),
    'utf8',
  );
  return new NextResponse(html, {
    headers: {
      'content-type': 'text/html; charset=utf-8',
    },
  });
}
