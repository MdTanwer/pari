import { NextResponse } from "next/server";

import { renderDocument, renderNotFound } from "../document";
import { pages } from "../pages";

type Context = {
  params: { slug?: string[] };
};

export function GET(_request: Request, context: Context) {
  const slug = (context.params.slug ?? []).join("/");
  const page = pages.get(slug);
  const html = page ? renderDocument(page) : renderNotFound();
  return new NextResponse(html, {
    status: page ? 200 : 404,
    headers: {
      "content-type": "text/html; charset=utf-8",
    },
  });
}
