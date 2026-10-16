/** Small HTML helpers for the docs pages. Content is static. */

let seq = 0;

export function beginDocument(): void {
  seq = 0;
}

export function esc(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

export function c(value: string): string {
  return `<code>${esc(value)}</code>`;
}

export function h2(id: string, title: string): string {
  return `<h2 id="${id}">${esc(title)}</h2>`;
}

export function h3(title: string): string {
  return `<h3>${esc(title)}</h3>`;
}

export function code(source: string): string {
  const text = source.replace(/^\n/, "").replace(/\n$/, "");
  const id = `code-${++seq}`;
  return (
    `<div class="codeblock">` +
    `<button type="button" class="copy" data-copy="${id}">Copy</button>` +
    `<pre id="${id}"><code>${esc(text)}</code></pre>` +
    `</div>`
  );
}

export function callout(kind: "warning" | "note", html: string): string {
  const label = kind === "warning" ? "Warning" : "Note";
  return (
    `<aside class="callout ${kind}">` +
    `<p class="callout-label">${label}</p>${html}</aside>`
  );
}

export function table(headers: string[], rows: string[][]): string {
  const head = headers.map((header) => `<th>${esc(header)}</th>`).join("");
  const body = rows
    .map(
      (row) =>
        `<tr>${row.map((cell) => `<td>${cell}</td>`).join("")}</tr>`,
    )
    .join("");
  return (
    `<div class="table-wrap"><table><thead><tr>${head}</tr></thead>` +
    `<tbody>${body}</tbody></table></div>`
  );
}

export function tabs(panels: { title: string; body: string }[]): string {
  const group = ++seq;
  const buttons = panels
    .map((panel, index) => {
      const selected = index === 0 ? "true" : "false";
      return (
        `<button type="button" role="tab" id="tab-${group}-${index}" ` +
        `aria-controls="panel-${group}-${index}" aria-selected="${selected}">` +
        `${esc(panel.title)}</button>`
      );
    })
    .join("");
  const bodies = panels
    .map((panel, index) => {
      const hidden = index === 0 ? "" : " hidden";
      return (
        `<div class="tabpanel" role="tabpanel" id="panel-${group}-${index}" ` +
        `aria-labelledby="tab-${group}-${index}"${hidden}>${panel.body}</div>`
      );
    })
    .join("");
  return (
    `<div class="tabs"><div class="tablist" role="tablist">${buttons}</div>` +
    `${bodies}</div>`
  );
}

export function steps(items: string[]): string {
  const list = items.map((item) => `<li>${item}</li>`).join("");
  return `<ol class="steps">${list}</ol>`;
}

export function next(links: { href: string; title: string; text: string }[]): string {
  const items = links
    .map(
      (link) =>
        `<li><a href="${esc(link.href)}">${esc(link.title)} ` +
        `<span class="arrow">→</span></a><p>${esc(link.text)}</p></li>`,
    )
    .join("");
  return `<ul class="next">${items}</ul>`;
}
