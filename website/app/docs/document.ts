import { esc } from "./markup";
import { nav, type DocPage } from "./pages";

const css = `
  :root {
    --mist: #EEF1F4;
    --ink: #111B1E;
    --muted: #52606F;
    --soft-muted: #788593;
    --moss: #687B60;
    --moss-dark: #43563D;
    --line: #CFD7DD;
    --line-soft: rgba(133, 148, 157, .24);
    --terminal: #172124;
    --lime: #A7DB69;
    --white: #F8FAFB;
    --shadow: 0 22px 70px rgba(50, 67, 75, .08);
    --warn: #8A6232;
    --warn-bg: rgba(196, 161, 90, .14);
  }
  * { box-sizing: border-box; }
  html { scroll-behavior: smooth; }
  body {
    margin: 0;
    background:
      radial-gradient(ellipse at 63% 22%, rgba(255,255,255,.78), transparent 34%),
      linear-gradient(120deg, #E9EEF2 0%, var(--mist) 49%, #EAF0F3 100%);
    color: var(--ink);
    font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    -webkit-font-smoothing: antialiased;
  }
  a { color: inherit; }
  button { font: inherit; }
  .page { width: min(1440px, calc(100% - 64px)); margin: 0 auto; }
  .nav {
    min-height: 77px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 26px;
    border-bottom: 1px solid var(--line);
  }
  .brand { display: flex; align-items: baseline; gap: 8px; flex-shrink: 0; text-decoration: none; }
  .brand-name { font-size: 39px; font-weight: 750; letter-spacing: -2.8px; line-height: 1; }
  .brand-dot { color: var(--moss); }
  .brand-cli { color: var(--muted); font: 12px/1.2 "SFMono-Regular", Consolas, monospace; letter-spacing: .04em; }
  .nav-links { display: flex; align-items: center; gap: clamp(20px, 3vw, 48px); font-size: 13px; color: #263138; }
  .nav-links a, .footer-links a { text-decoration: none; transition: color .2s ease; }
  .nav-links a:hover, .footer-links a:hover, .nav-links a[aria-current="page"] { color: var(--moss); }
  .github-link { display: inline-flex; align-items: center; gap: 6px; }
  .github-link svg { width: 15px; height: 15px; flex-shrink: 0; transition: transform .2s ease; }
  .github-link:hover svg { transform: translateY(-1px); }
  .github-mark {
    display: none; width: 36px; height: 36px; border-radius: 50%;
    color: #56656B; place-items: center; text-decoration: none;
  }
  .github-mark svg { width: 18px; height: 18px; display: block; }
  .github-mark:hover { background: rgba(255,255,255,.7); color: var(--moss); }
  .nav-right { display: flex; align-items: center; gap: 20px; }
  .theme-toggle {
    width: 36px; height: 36px; border: 0; background: transparent; color: #56656B;
    display: grid; place-items: center; cursor: pointer; border-radius: 50%;
  }
  .theme-toggle:hover { background: rgba(255,255,255,.7); }
  .theme-toggle svg { width: 18px; height: 18px; display: block; }
  .theme-toggle .icon-sun { display: none; }
  body.dark .theme-toggle, body.dark .github-mark { color: #D5DEDC; }
  body.dark .theme-toggle:hover, body.dark .github-mark:hover { background: rgba(255,255,255,.08); }
  body.dark .github-mark:hover, body.dark .github-link:hover { color: var(--moss); }
  body.dark .theme-toggle .icon-moon { display: none; }
  body.dark .theme-toggle .icon-sun { display: block; }
  .btn {
    display: inline-flex; align-items: center; justify-content: center; gap: 13px;
    border: 1px solid transparent; border-radius: 7px; padding: 15px 22px;
    font-size: 14px; font-weight: 550; cursor: pointer; text-decoration: none;
    transition: transform .2s ease, background .2s ease; white-space: nowrap;
  }
  .btn:hover { transform: translateY(-1px); }
  .btn-dark { background: #202A2B; color: white; box-shadow: 0 4px 10px rgba(15, 26, 29, .08); }
  .btn-dark:hover { background: #30403D; }
  .arrow { font-size: 19px; line-height: 10px; font-weight: 300; }

  .docs {
    display: grid;
    grid-template-columns: 220px minmax(0, 1fr);
    gap: 48px;
    padding: 34px 0 64px;
    align-items: start;
  }
  .sidebar { position: sticky; top: 18px; }
  .side-label {
    margin: 18px 0 8px;
    color: var(--moss-dark);
    font: 11px "SFMono-Regular", Consolas, monospace;
    letter-spacing: .08em;
    text-transform: uppercase;
  }
  .side-label:first-child { margin-top: 0; }
  .sidebar a {
    display: block;
    padding: 6px 0;
    color: #263138;
    text-decoration: none;
    font-size: 14px;
  }
  .sidebar a:hover, .sidebar a[aria-current="page"] { color: var(--moss-dark); }
  .sidebar a[aria-current="page"] { font-weight: 600; }
  .doc { min-width: 0; max-width: 820px; }
  .eyebrow {
    color: var(--moss-dark);
    font: 12px/1.4 "SFMono-Regular", Consolas, monospace;
    letter-spacing: .11em;
    text-transform: uppercase;
  }
  h1 {
    font-size: clamp(36px, 4vw, 52px);
    letter-spacing: -.05em;
    line-height: 1.05;
    font-weight: 590;
    margin: 14px 0 12px;
  }
  .lede { color: var(--muted); font-size: 18px; line-height: 1.55; margin: 0 0 22px; }
  h2 {
    font-size: 26px;
    letter-spacing: -.03em;
    font-weight: 590;
    margin: 36px 0 12px;
    scroll-margin-top: 18px;
  }
  h3 { font-size: 16px; margin: 22px 0 8px; }
  p { color: var(--muted); line-height: 1.6; margin: 0 0 14px; }
  p a, .callout a, li a { color: var(--moss-dark); }
  code {
    font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
    font-size: .92em;
  }
  p code, li code, td code {
    background: rgba(104, 123, 96, .12);
    border-radius: 4px;
    padding: 1px 5px;
  }
  .callout {
    border: 1px solid var(--line);
    border-left: 3px solid var(--moss);
    border-radius: 8px;
    background: rgba(255,255,255,.35);
    padding: 14px 16px 2px;
    margin: 0 0 22px;
  }
  .callout.warning { border-left-color: var(--warn); background: var(--warn-bg); }
  .callout-label {
    margin: 0 0 6px;
    font: 11px "SFMono-Regular", Consolas, monospace;
    letter-spacing: .08em;
    text-transform: uppercase;
    color: var(--moss-dark);
  }
  .callout.warning .callout-label { color: var(--warn); }
  .callout p:last-child { margin-bottom: 12px; }
  .table-wrap { overflow-x: auto; margin: 0 0 18px; }
  table { width: 100%; border-collapse: collapse; font-size: 14px; }
  th, td {
    text-align: left;
    vertical-align: top;
    padding: 12px 14px;
    border-bottom: 1px solid var(--line);
  }
  th {
    color: var(--moss-dark);
    font: 11px "SFMono-Regular", Consolas, monospace;
    letter-spacing: .06em;
    text-transform: uppercase;
    font-weight: 500;
  }
  td { color: var(--muted); line-height: 1.5; }
  .tabs { margin: 0 0 8px; }
  .tablist { display: flex; flex-wrap: wrap; gap: 8px; margin: 0 0 12px; }
  .tablist button {
    border: 1px solid var(--line);
    background: rgba(255,255,255,.28);
    color: var(--muted);
    border-radius: 7px;
    padding: 7px 12px;
    cursor: pointer;
    font-size: 13px;
  }
  .tablist button[aria-selected="true"] {
    color: var(--ink);
    border-color: var(--moss);
    background: rgba(104, 123, 96, .12);
  }
  .codeblock {
    position: relative;
    margin: 0 0 16px;
    border-radius: 8px;
    background: linear-gradient(145deg, #1D292C, var(--terminal));
    border: 1px solid rgba(255,255,255,.08);
    box-shadow: var(--shadow);
  }
  .codeblock pre {
    margin: 0;
    padding: 16px 18px;
    overflow-x: auto;
    color: #E7EEF0;
    font: 13px/1.7 "SFMono-Regular", Consolas, "Liberation Mono", monospace;
  }
  .codeblock code { background: transparent; padding: 0; color: inherit; }
  .copy {
    position: absolute;
    top: 8px;
    right: 8px;
    border: 1px solid rgba(255,255,255,.14);
    background: rgba(255,255,255,.06);
    color: #C3CDD0;
    border-radius: 6px;
    padding: 4px 8px;
    font: 11px "SFMono-Regular", Consolas, monospace;
    letter-spacing: .04em;
    cursor: pointer;
  }
  .copy:hover { color: var(--lime); }
  ol.steps { margin: 0 0 18px; padding: 0; list-style: none; counter-reset: step; }
  ol.steps li {
    counter-increment: step;
    display: grid;
    grid-template-columns: 36px 1fr;
    gap: 8px;
    padding: 10px 0;
    border-bottom: 1px solid var(--line-soft);
    color: var(--muted);
    line-height: 1.5;
  }
  ol.steps li::before {
    content: counter(step, decimal-leading-zero);
    color: var(--moss-dark);
    font: 12px "SFMono-Regular", Consolas, monospace;
    padding-top: 3px;
  }
  ul.next { list-style: none; margin: 8px 0 0; padding: 0; display: grid; gap: 12px; }
  ul.next li {
    border: 1px solid var(--line);
    border-radius: 8px;
    background: rgba(255,255,255,.28);
    padding: 14px 16px;
  }
  ul.next a { color: var(--ink); text-decoration: none; font-weight: 590; }
  ul.next a:hover { color: var(--moss-dark); }
  ul.next p { margin: 6px 0 0; font-size: 14px; }
  .footer {
    display: flex; align-items: center; justify-content: space-between; gap: 20px;
    padding: 22px 0 28px; border-top: 1px solid var(--line); color: var(--muted); font-size: 12px;
  }
  .footer-links { display: flex; gap: 22px; }

  body.dark {
    --mist: #121819; --ink: #E8EEED; --muted: #A8B4B6; --soft-muted: #829092;
    --moss: #A4C58D; --moss-dark: #B3CBA2; --line: #354143; --line-soft: rgba(154,172,173,.2);
    --warn: #E2C48A; --warn-bg: rgba(226, 196, 138, .08);
    background: radial-gradient(ellipse at 63% 22%, rgba(59,75,73,.25), transparent 36%), #121819;
  }
  body.dark .nav-links, body.dark .sidebar a, body.dark .btn-dark { color: #E0E8E6; }
  body.dark .sidebar a[aria-current="page"], body.dark .sidebar a:hover { color: var(--moss); }
  body.dark .btn-dark { background: #DCE9D5; color: #17201B; }
  body.dark .btn-dark:hover { background: #C6DDBA; }
  body.dark .brand-cli { color: #A8B4B6; }
  body.dark .callout, body.dark ul.next li, body.dark .tablist button { background: rgba(255,255,255,.03); border-color: #354143; }
  body.dark .tablist button[aria-selected="true"] { color: #E8EEED; border-color: var(--moss); }
  body.dark p code, body.dark li code, body.dark td code { background: rgba(164, 197, 141, .12); }

  @media (max-width: 1120px) {
    .page { width: min(100% - 40px, 1000px); }
    .nav-links { gap: 18px; }
  }
  @media (max-width: 860px) {
    .docs { grid-template-columns: 1fr; gap: 18px; }
    .sidebar { position: static; display: flex; gap: 18px; overflow-x: auto; padding-bottom: 8px; }
    .side-group { flex: 0 0 auto; }
    .sidebar a { white-space: nowrap; }
  }
  @media (max-width: 720px) {
    .page { width: calc(100% - 32px); }
    .nav { min-height: 68px; }
    .brand-name { font-size: 32px; }
    .nav-links { display: none; }
    .github-mark { display: grid; }
    .nav-right .btn { padding: 12px 13px; font-size: 12px; }
    h1 { font-size: 36px; }
    .footer { align-items: flex-start; flex-direction: column; }
  }
  @media (prefers-reduced-motion: reduce) {
    *, *::before, *::after { scroll-behavior: auto !important; animation: none !important; transition: none !important; }
  }
`;

const script = `
  const toggle = document.getElementById("themeToggle");
  if (localStorage.getItem("pari-theme") === "dark") document.body.classList.add("dark");
  function syncLabel() {
    const dark = document.body.classList.contains("dark");
    const label = dark ? "Switch to light mode" : "Switch to dark mode";
    toggle.setAttribute("aria-label", label);
    toggle.setAttribute("title", label);
  }
  syncLabel();
  toggle.addEventListener("click", () => {
    document.body.classList.toggle("dark");
    localStorage.setItem("pari-theme", document.body.classList.contains("dark") ? "dark" : "light");
    syncLabel();
  });
  document.getElementById("year").textContent = new Date().getFullYear();
  document.querySelectorAll(".tabs").forEach((group) => {
    const tabs = [...group.querySelectorAll("[role=tab]")];
    const panels = [...group.querySelectorAll("[role=tabpanel]")];
    tabs.forEach((tab, index) => {
      tab.addEventListener("click", () => {
        tabs.forEach((item, itemIndex) => {
          const selected = itemIndex === index;
          item.setAttribute("aria-selected", selected ? "true" : "false");
          panels[itemIndex].hidden = !selected;
        });
      });
    });
  });
  document.querySelectorAll("[data-copy]").forEach((button) => {
    button.addEventListener("click", async () => {
      const block = document.getElementById(button.getAttribute("data-copy"));
      const text = block ? block.innerText : "";
      try {
        await navigator.clipboard.writeText(text);
        button.textContent = "Copied";
      } catch {
        button.textContent = "Copy";
      }
      setTimeout(() => { button.textContent = "Copy"; }, 1600);
    });
  });
`;

function sidebar(current: string): string {
  return nav
    .map((group) => {
      const links = group.items
        .map((item) => {
          const currentAttr = item.slug === current ? ' aria-current="page"' : "";
          return `<a href="${item.href}"${currentAttr}>${esc(item.title)}</a>`;
        })
        .join("");
      return `<div class="side-group"><p class="side-label">${esc(group.label)}</p>${links}</div>`;
    })
    .join("");
}

function shell(title: string, description: string, main: string): string {
  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta name="theme-color" content="#EEF1F4" />
  <meta name="description" content="${esc(description)}" />
  <title>${esc(title)} — PARI CLI</title>
  <style>${css}</style>
</head>
<body>
  <div class="page">
    <header class="nav">
      <a class="brand" href="/" aria-label="PARI CLI home">
        <span class="brand-name">pari<span class="brand-dot">.</span></span>
        <span class="brand-cli">CLI</span>
      </a>
      <nav class="nav-links" aria-label="Main navigation">
        <a href="/#overview">Overview</a>
        <a href="/docs" aria-current="page">Docs</a>
        <a class="github-link" href="https://github.com/MdTanwer/pari" target="_blank" rel="noopener noreferrer"><svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 .8a11.2 11.2 0 0 0-3.54 21.83c.56.1.77-.24.77-.54v-2.1c-3.14.68-3.8-1.33-3.8-1.33-.51-1.3-1.25-1.65-1.25-1.65-1.02-.7.08-.69.08-.69 1.13.08 1.73 1.16 1.73 1.16 1 .1.76 2.1 3.28 1.6.1-.74.4-1.24.72-1.52-2.5-.28-5.13-1.25-5.13-5.56 0-1.23.44-2.24 1.16-3.03-.12-.28-.5-1.43.11-2.98 0 0 .95-.3 3.08 1.16a10.7 10.7 0 0 1 5.6 0c2.13-1.45 3.08-1.16 3.08-1.16.61 1.55.23 2.7.11 2.98.72.79 1.16 1.8 1.16 3.03 0 4.32-2.63 5.28-5.14 5.56.4.35.77 1.03.77 2.08v3.08c0 .3.2.65.78.54A11.2 11.2 0 0 0 12 .8Z"/></svg>GitHub</a>
      </nav>
      <div class="nav-right">
        <a class="github-mark" href="https://github.com/MdTanwer/pari" target="_blank" rel="noopener noreferrer" aria-label="GitHub"><svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 .8a11.2 11.2 0 0 0-3.54 21.83c.56.1.77-.24.77-.54v-2.1c-3.14.68-3.8-1.33-3.8-1.33-.51-1.3-1.25-1.65-1.25-1.65-1.02-.7.08-.69.08-.69 1.13.08 1.73 1.16 1.73 1.16 1 .1.76 2.1 3.28 1.6.1-.74.4-1.24.72-1.52-2.5-.28-5.13-1.25-5.13-5.56 0-1.23.44-2.24 1.16-3.03-.12-.28-.5-1.43.11-2.98 0 0 .95-.3 3.08 1.16a10.7 10.7 0 0 1 5.6 0c2.13-1.45 3.08-1.16 3.08-1.16.61 1.55.23 2.7.11 2.98.72.79 1.16 1.8 1.16 3.03 0 4.32-2.63 5.28-5.14 5.56.4.35.77 1.03.77 2.08v3.08c0 .3.2.65.78.54A11.2 11.2 0 0 0 12 .8Z"/></svg></a>
        <button class="theme-toggle" id="themeToggle" aria-label="Switch to dark mode" title="Switch to dark mode">
          <svg class="icon-moon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 14.5A8.5 8.5 0 1 1 9.5 3a7 7 0 0 0 11.5 11.5z"/></svg>
          <svg class="icon-sun" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"/></svg>
        </button>
        <a class="btn btn-dark" href="/docs/setup">Install <span class="arrow">→</span></a>
      </div>
    </header>
    ${main}
    <footer class="footer">
      <span>© <span id="year"></span> PARI CLI · Engineered for dependable code changes.</span>
      <div class="footer-links">
        <a href="/docs">Documentation</a>
        <a href="/docs/setup">Install</a>
        <a href="/docs/troubleshooting">Troubleshooting</a>
        <a class="github-link" href="https://github.com/MdTanwer/pari" target="_blank" rel="noopener noreferrer"><svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 .8a11.2 11.2 0 0 0-3.54 21.83c.56.1.77-.24.77-.54v-2.1c-3.14.68-3.8-1.33-3.8-1.33-.51-1.3-1.25-1.65-1.25-1.65-1.02-.7.08-.69.08-.69 1.13.08 1.73 1.16 1.73 1.16 1 .1.76 2.1 3.28 1.6.1-.74.4-1.24.72-1.52-2.5-.28-5.13-1.25-5.13-5.56 0-1.23.44-2.24 1.16-3.03-.12-.28-.5-1.43.11-2.98 0 0 .95-.3 3.08 1.16a10.7 10.7 0 0 1 5.6 0c2.13-1.45 3.08-1.16 3.08-1.16.61 1.55.23 2.7.11 2.98.72.79 1.16 1.8 1.16 3.03 0 4.32-2.63 5.28-5.14 5.56.4.35.77 1.03.77 2.08v3.08c0 .3.2.65.78.54A11.2 11.2 0 0 0 12 .8Z"/></svg>GitHub</a>
      </div>
    </footer>
  </div>
  <script>${script}</script>
</body>
</html>`;
}

export function renderDocument(page: DocPage): string {
  const main = `
    <main class="docs">
      <nav class="sidebar" aria-label="Documentation">
        ${sidebar(page.slug)}
      </nav>
      <article class="doc">
        <p class="eyebrow">${esc(page.eyebrow)}</p>
        <h1>${esc(page.title)}</h1>
        ${page.body}
      </article>
    </main>`;
  return shell(page.title, page.description, main);
}

export function renderNotFound(): string {
  const main = `
    <main class="docs">
      <nav class="sidebar" aria-label="Documentation">${sidebar("")}</nav>
      <article class="doc">
        <p class="eyebrow">Documentation</p>
        <h1>Page not found</h1>
        <p class="lede">That guide is not on this site. Start with the install page.</p>
        <ul class="next"><li><a href="/docs/setup">Install PARI <span class="arrow">→</span></a><p>Choose an install method and confirm the CLI starts.</p></li></ul>
      </article>
    </main>`;
  return shell("Page not found", "That documentation page does not exist.", main);
}
