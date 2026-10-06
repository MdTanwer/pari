'use client';

import React, { useState } from 'react';
import {
  Terminal,
  Shield,
  Zap,
  Copy,
  Check,
  ExternalLink,
  Code
} from 'lucide-react';

export default function HomePage() {
  const [activeTab, setActiveTab] = useState<'curl' | 'irm' | 'pip' | 'uv'>('curl');
  const [copiedTab, setCopiedTab] = useState<string | null>(null);

  const installCommands = {
    curl: 'curl -fsSL https://pari-cli.in/install.sh | bash',
    irm: 'irm https://pari-cli.in/install.ps1 | iex',
    pip: 'pip install pari-cli',
    uv: 'uv tool install pari-cli'
  };

  const handleCopy = (key: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedTab(key);
    setTimeout(() => setCopiedTab(null), 2000);
  };





  return (
    <div style={{ position: 'relative' }}>
      <div className="bg-glow-top" />
      <div className="bg-glow-mid" />
      <div className="grid-bg" />

      {/* Navigation */}
      <header className="navbar">
        <div className="container nav-container">
          <a href="#" className="logo-group">
            <span className="logo-badge">PARI</span>
            <span className="logo-name">pari-cli</span>
            <span className="logo-tag">v0.1.2</span>
          </a>

          <nav className="nav-links">
            <a href="#install" className="nav-link">Install</a>
            <a href="#tui" className="nav-link">Terminal TUI</a>
            <a href="#platforms" className="nav-link">Platforms</a>
            <a href="https://pypi.org/project/pari-cli/" target="_blank" rel="noreferrer" className="nav-link">
              PyPI <ExternalLink style={{ display: 'inline', width: 14, height: 14, verticalAlign: 'middle' }} />
            </a>
          </nav>

          <a
            href="https://github.com/MdTanwer/pari"
            target="_blank"
            rel="noreferrer"
            className="btn-nav-github"
          >
            <Code style={{ width: 16, height: 16 }} />
            <span>GitHub</span>
          </a>
        </div>
      </header>

      {/* Hero Section */}
      <section className="hero-section">
        <div className="container">
          <div className="hero-pill">
            <span className="hero-pill-dot" />
            <span>Frontier Terminal Coding Agent</span>
          </div>

          <h1 className="hero-title">
            The Autonomous <span className="gradient-text">Terminal Coding Agent</span> for Production Repositories.
          </h1>

          <p className="hero-subtitle">
            Engineered with kernel sandboxing, deterministic AST code navigation, and durable Merkle DAG sessions. Fast, local, and zero-token waste.
          </p>

          {/* Interactive Install Box */}
          <div id="install" className="terminal-box">
            <div className="terminal-header">
              <div className="terminal-dots">
                <span className="dot dot-red" />
                <span className="dot dot-yellow" />
                <span className="dot dot-green" />
              </div>
              <div className="terminal-tabs">
                {(['curl', 'irm', 'pip', 'uv'] as const).map((tab) => (
                  <button
                    key={tab}
                    onClick={() => setActiveTab(tab)}
                    className={`tab-btn ${activeTab === tab ? 'active' : ''}`}
                  >
                    {tab === 'curl' && 'macOS / Linux (curl)'}
                    {tab === 'irm' && 'Windows (irm)'}
                    {tab === 'pip' && 'pip'}
                    {tab === 'uv' && 'uv tool'}
                  </button>
                ))}
              </div>
            </div>

            <div className="terminal-body">
              <div className="terminal-prompt-line">
                <span className="prompt-symbol">$</span>
                <span className="prompt-text">{installCommands[activeTab]}</span>
              </div>
              <button
                className="btn-copy"
                onClick={() => handleCopy(activeTab, installCommands[activeTab])}
              >
                {copiedTab === activeTab ? (
                  <>
                    <Check style={{ width: 14, height: 14, color: '#34d399' }} />
                    <span style={{ color: '#34d399' }}>Copied!</span>
                  </>
                ) : (
                  <>
                    <Copy style={{ width: 14, height: 14 }} />
                    <span>Copy</span>
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Stats Bar */}
          <div className="stats-row">
            <div className="stat-card">
              <div className="stat-number">55%</div>
              <div className="stat-label">Harness Pass Rate</div>
            </div>
            <div className="stat-card">
              <div className="stat-number">0ms</div>
              <div className="stat-label">Telemetry Delay</div>
            </div>
            <div className="stat-card">
              <div className="stat-number">85%</div>
              <div className="stat-label">Token Cost Savings</div>
            </div>
            <div className="stat-card">
              <div className="stat-number">0%</div>
              <div className="stat-label">Idle CPU Drain</div>
            </div>
          </div>
        </div>
      </section>

      {/* Live Terminal TUI Experience */}
      <section id="tui" className="container" style={{ marginBottom: 100 }}>
        <div className="section-header">
          <span className="section-tag">Differential TUI</span>
          <h2 className="section-title">A Lightning-Fast Terminal Interface</h2>
          <p className="section-desc">
            No Electron bloat, no background CPU pegging. Built on Python prompt_toolkit & Rich with instant autocomplete suggestions and unified diff previews.
          </p>
        </div>

        <div className="interactive-demo">
          <div className="terminal-header">
            <div className="terminal-dots">
              <span className="dot dot-red" />
              <span className="dot dot-yellow" />
              <span className="dot dot-green" />
            </div>
            <span style={{ fontSize: '0.8rem', color: '#64748b', fontFamily: 'var(--font-mono)' }}>
              pari-cli interactive REPL session
            </span>
          </div>

          <div className="demo-screen">
            <div className="demo-output-banner">
              PARI v0.1.2 — Coding Agent (https://pari-cli.in)
            </div>
            <div className="demo-meta-row">
              <span style={{ color: '#64748b' }}>Workspace : </span>
              <span className="demo-meta-val">~/projects/my-app</span>
            </div>
            <div className="demo-meta-row">
              <span style={{ color: '#64748b' }}>Model     : </span>
              <span style={{ color: '#34d399' }}>pari-core default · 1.5k tokens · $0.009</span>
            </div>

            <div style={{ margin: '20px 0 10px 0', display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ color: '#38bdf8', fontWeight: 'bold' }}>&gt;</span>
              <span style={{ color: '#ffffff' }}>/</span>
              <span style={{ display: 'inline-block', width: 8, height: 18, background: '#ffffff', verticalAlign: 'middle', animation: 'pulse 1s infinite' }} />
            </div>

            {/* Dropdown Menu */}
            <div className="demo-dropdown">
              <div className="dropdown-item active">
                <span className="item-cmd">&gt; /help</span>
                <span className="item-desc">Show available slash commands and help overview</span>
              </div>
              <div className="dropdown-item">
                <span className="item-cmd">  /diff</span>
                <span className="item-desc">Preview pending or latest unified diffs</span>
              </div>
              <div className="dropdown-item">
                <span className="item-cmd">  /undo</span>
                <span className="item-desc">Revert the most recent file change</span>
              </div>
              <div className="dropdown-item">
                <span className="item-cmd">  /model</span>
                <span className="item-desc">Inspect or switch active LLM provider</span>
              </div>
              <div className="dropdown-item">
                <span className="item-cmd">  /clear</span>
                <span className="item-desc">Clear terminal screen & reset active view</span>
              </div>
            </div>

            <div className="demo-footer-hints">
              <span><span className="hint-key">↑/↓</span> Navigate</span>
              <span>·</span>
              <span><span className="hint-key">enter</span> Select</span>
              <span>·</span>
              <span><span className="hint-key">tab</span> Complete</span>
              <span>·</span>
              <span><span style={{ color: '#94a3b8' }}>esc</span> to cancel</span>
            </div>
          </div>
        </div>
      </section>

      {/* Universal Compatibility Section */}
      <section id="platforms" className="container install-section">
        <div className="section-header">
          <span className="section-tag">Cross-Platform</span>
          <h2 className="section-title">Install on Any Machine in Seconds</h2>
          <p className="section-desc">
            Universal native support across macOS, Linux, and Windows PowerShell without manual environment configuration.
          </p>
        </div>

        <div className="install-grid">
          <div className="install-card">
            <div className="install-platform">
              <Terminal style={{ width: 20, height: 20, color: '#38bdf8' }} />
              <span>macOS & Linux (curl)</span>
            </div>
            <p style={{ color: '#94a3b8', fontSize: '0.88rem', marginBottom: 12 }}>
              Automatic shell detection for zsh, bash, and fish with duplicate PATH protection.
            </p>
            <div className="install-snippet">
              <code>curl -fsSL https://pari-cli.in/install.sh | bash</code>
              <button
                className="btn-copy"
                onClick={() => handleCopy('curl-card', 'curl -fsSL https://pari-cli.in/install.sh | bash')}
              >
                {copiedTab === 'curl-card' ? 'Copied' : <Copy style={{ width: 14, height: 14 }} />}
              </button>
            </div>
          </div>

          <div className="install-card">
            <div className="install-platform">
              <Shield style={{ width: 20, height: 20, color: '#34d399' }} />
              <span>Windows (PowerShell)</span>
            </div>
            <p style={{ color: '#94a3b8', fontSize: '0.88rem', marginBottom: 12 }}>
              Native PowerShell installer with WindowsApps stub bypass & automatic PATH config.
            </p>
            <div className="install-snippet">
              <code>irm https://pari-cli.in/install.ps1 | iex</code>
              <button
                className="btn-copy"
                onClick={() => handleCopy('irm-card', 'irm https://pari-cli.in/install.ps1 | iex')}
              >
                {copiedTab === 'irm-card' ? 'Copied' : <Copy style={{ width: 14, height: 14 }} />}
              </button>
            </div>
          </div>

          <div className="install-card">
            <div className="install-platform">
              <Zap style={{ width: 20, height: 20, color: '#fbbf24' }} />
              <span>PyPI / Python Ecosystem</span>
            </div>
            <p style={{ color: '#94a3b8', fontSize: '0.88rem', marginBottom: 12 }}>
              Standard distribution published live on the Python Package Index.
            </p>
            <div className="install-snippet">
              <code>pip install pari-cli</code>
              <button
                className="btn-copy"
                onClick={() => handleCopy('pip-card', 'pip install pari-cli')}
              >
                {copiedTab === 'pip-card' ? 'Copied' : <Copy style={{ width: 14, height: 14 }} />}
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="footer">
        <div className="container">
          <div className="footer-top">
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span className="logo-badge">PARI</span>
              <span style={{ fontWeight: 600, color: '#f8fafc' }}>pari-cli.in</span>
            </div>

            <div className="footer-links">
              <a href="https://github.com/MdTanwer/pari" target="_blank" rel="noreferrer" className="footer-link">GitHub</a>
              <a href="https://pypi.org/project/pari-cli/" target="_blank" rel="noreferrer" className="footer-link">PyPI</a>
              <a href="#install" className="footer-link">Install</a>
              <a href="#platforms" className="footer-link">Platforms</a>
            </div>
          </div>

          <div style={{ textAlign: 'center', fontSize: '0.85rem', color: '#64748b' }}>
            © {new Date().getFullYear()} PARI Contributors. Released under the MIT License. Built for world-class systems engineering performance.
          </div>
        </div>
      </footer>
    </div>
  );
}
