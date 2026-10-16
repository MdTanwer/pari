import {
  beginDocument,
  c,
  callout,
  code,
  h2,
  h3,
  next,
  steps,
  table,
  tabs,
} from "./markup";

export type DocPage = {
  slug: string;
  title: string;
  description: string;
  eyebrow: string;
  body: string;
};

export type NavGroup = {
  label: string;
  items: { href: string; title: string; slug: string }[];
};

export const nav: NavGroup[] = [
  {
    label: "Start",
    items: [
      { href: "/docs", title: "Overview", slug: "" },
      { href: "/docs/setup", title: "Install", slug: "setup" },
      { href: "/docs/first-session", title: "First session", slug: "first-session" },
    ],
  },
  {
    label: "Use",
    items: [
      { href: "/docs/commands", title: "Commands", slug: "commands" },
      { href: "/docs/models", title: "Models", slug: "models" },
      { href: "/docs/sandbox", title: "Sandbox", slug: "sandbox" },
      { href: "/docs/permissions", title: "Permissions", slug: "permissions" },
    ],
  },
  {
    label: "Help",
    items: [
      {
        href: "/docs/troubleshooting",
        title: "Troubleshooting",
        slug: "troubleshooting",
      },
    ],
  },
];

function overview(): string {
  beginDocument();
  return `
    <p class="lede">PARI is a terminal coding agent. You open a repository, sign in to a model, and ask it to search, edit, and run commands in that project.</p>
    ${callout(
      "warning",
      `<p>Treat the agent as untrusted. It can read files, write files, and run shell commands in the workspace you open. On Linux those commands stay inside Bubblewrap. If Bubblewrap is missing, or the host is not Linux, PARI does not run the command on your account. macOS Seatbelt and the Windows supervised runner are not available yet.</p>`,
    )}
    ${h2("start-here", "Start here")}
    <p>Install the CLI, confirm Python and Bubblewrap, sign in, then start a session in the repository you want changed.</p>
    ${table(
      ["Guide", "Use it when"],
      [
        [
          `<a href="/docs/setup">Install</a>`,
          "You need to install, update, or remove PARI.",
        ],
        [
          `<a href="/docs/first-session">First session</a>`,
          "The CLI is installed and you want to run a task.",
        ],
        [
          `<a href="/docs/commands">Commands</a>`,
          "You want the flags and the in-session slash commands.",
        ],
        [
          `<a href="/docs/models">Models</a>`,
          "You are choosing DeepSeek, OpenAI, Anthropic, Grok, or OpenRouter.",
        ],
        [
          `<a href="/docs/sandbox">Sandbox</a>`,
          "You want to know what a command can see and touch.",
        ],
        [
          `<a href="/docs/permissions">Permissions</a>`,
          "You want the built-in rules, the ones you write, and the prompt.",
        ],
      ],
    )}
    ${h2("what-a-session-does", "What a session does")}
    <p>From the project directory, ${c("pari-cli")} opens a prompt. A normal turn looks like this:</p>
    ${steps([
      "You describe the change in plain language.",
      "PARI searches the repository and reads the files it needs.",
      "It edits files in that workspace.",
      "It runs shell commands inside the Linux Bubblewrap sandbox.",
      "You inspect the diff, undo the last change, or keep going.",
    ])}
    ${code(`cd ~/projects/my-app
pari-cli login
pari-cli`)}
    <p>The conversation is stored under ${c(".pari/")} in that project. Your API key is stored in ${c("~/.pari/auth.json")}, outside the project.</p>
    ${h2("where-it-runs", "Where it runs")}
    ${table(
      ["Host", "Install the CLI", "Run agent commands"],
      [
        [
          "Linux",
          "Yes",
          `Yes, with Bubblewrap from ${c("/usr/bin")} or ${c("/usr/local/bin")}.`,
        ],
        [
          "macOS",
          "Yes",
          "Not yet. Automatic mode refuses to run a command on the Mac host.",
        ],
        [
          "Windows",
          "Yes",
          "Use Ubuntu on WSL2 and install Bubblewrap there. Native Windows does not run commands on the host.",
        ],
      ],
    )}
    ${callout(
      "note",
      "<p>New to PARI? Install on Linux, or on Windows through WSL2, so the agent can actually run the project’s tests and tools.</p>",
    )}
    ${h2("next", "Next")}
    ${next([
      {
        href: "/docs/setup",
        title: "Install PARI",
        text: "Choose an install method, check prerequisites, and confirm the CLI starts.",
      },
      {
        href: "/docs/first-session",
        title: "First session",
        text: "Sign in, open a workspace, and ask for a change.",
      },
    ])}
  `;
}

function setup(): string {
  beginDocument();
  return `
    <p class="lede">Install, run, update, or uninstall PARI.</p>
    ${callout(
      "warning",
      `<p>Treat the agent as untrusted. It can run shell commands, read files, and write files in the workspace you open. PARI is the client. On Linux, commands run in Bubblewrap and the workspace is the only writable mount. Seatbelt, cloud sandboxes, and unsandboxed host execution are not available. If the sandbox cannot be applied, the command is refused.</p>`,
    )}
    ${h2("choose-an-install-method", "Choose an install method")}
    ${table(
      ["Method", "Use it when", "What the agent can access"],
      [
        [
          "<strong>curl</strong>",
          "You want the quickest setup on macOS or Linux.",
          "The project you launch from. On Linux, shell commands stay inside Bubblewrap.",
        ],
        [
          "<strong>PowerShell</strong>",
          "You are on Windows.",
          "Installs the CLI. Run the session inside WSL2 when you want Bubblewrap.",
        ],
        [
          "<strong>pipx</strong>",
          "You want an isolated, reusable command.",
          "Same workspace boundary as the installer you would have used.",
        ],
        [
          "<strong>uv</strong>",
          "You already use uv and want a fast install.",
          "Same workspace boundary.",
        ],
        [
          "<strong>pip</strong>",
          "You want PARI in the current Python environment.",
          "Same workspace boundary.",
        ],
        [
          "<strong>From source</strong>",
          "You are changing PARI itself.",
          "Your local checkout, with the same sandbox rules.",
        ],
      ],
    )}
    ${callout(
      "note",
      "<p>If you are new, use curl on Linux or pipx if you already manage Python tools that way. On Windows, install Ubuntu on WSL2 and use the Linux steps there. The native Windows install gives you the CLI, and command execution still waits for the Linux sandbox.</p>",
    )}
    ${h2("verify-prerequisites", "Verify prerequisites")}
    ${tabs([
      {
        title: "Linux",
        body: `
          <p>Install <a href="https://www.python.org/downloads/">Python</a> 3.11 or later, Git, and Bubblewrap. Then check that each one is on your PATH:</p>
          ${code(`python3 --version
git --version
bwrap --version`)}
          <p>Debian and Ubuntu:</p>
          ${code("sudo apt-get install bubblewrap")}
          <p>Fedora:</p>
          ${code("sudo dnf install bubblewrap")}
          <p>PARI only trusts Bubblewrap from ${c("/usr/bin")}, ${c("/usr/local/bin")}, or ${c("/bin")}. A copy inside the repository is ignored.</p>
        `,
      },
      {
        title: "macOS",
        body: `
          <p>Install Python 3.11 or later and confirm it:</p>
          ${code(`python3 --version
git --version`)}
          <p>You can install and sign in on a Mac. Automatic sandbox mode will not run shell commands on the Mac host. Use a Linux machine or a Linux VM when you want the agent to execute commands.</p>
        `,
      },
      {
        title: "Windows",
        body: `
          <p>Install Python 3.11 or later. In PowerShell:</p>
          ${code(`py -3 --version
git --version`)}
          <p>For a session that can run commands, install Ubuntu from WSL2, open that shell, install Bubblewrap, and follow the Linux steps inside it.</p>
        `,
      },
    ])}
    ${h2("install-and-run", "Install and run")}
    ${tabs([
      {
        title: "curl",
        body: `
          <p>Install the published package. The script uses uv if it is installed, then pipx, then a virtualenv in ${c("~/.pari/venv")} with a link in ${c("~/.local/bin")}.</p>
          ${code(`curl -fsSL https://pari-cli.in/install.sh | bash
pari-cli --version`)}
          <p>Open a new terminal if the shell says ${c("pari-cli")} was not found. The installer adds ${c("~/.local/bin")} to bash or zsh when that directory is missing from ${c("PATH")}.</p>
        `,
      },
      {
        title: "PowerShell",
        body: `
          <p>The Windows script follows the same order: uv, then pipx, then a virtualenv in your user profile at ${c(".pari")}.</p>
          ${code(`irm https://www.pari-cli.in/install.ps1 | iex
pari-cli --version`)}
        `,
      },
      {
        title: "pipx",
        body: `
          <p>pipx keeps PARI out of the environment you use for other projects.</p>
          ${code(`pipx install pari-cli
pari-cli --version`)}
        `,
      },
      {
        title: "uv",
        body: `
          ${code(`uv tool install pari-cli
pari-cli --version`)}
        `,
      },
      {
        title: "pip",
        body: `
          ${code(`pip install pari-cli
pari-cli --version`)}
        `,
      },
      {
        title: "From source",
        body: `
          <p>Use a checkout when you are changing PARI. Python 3.11 or later is required.</p>
          ${code(`git clone https://github.com/MdTanwer/pari.git
cd pari
python3 -m venv .venv
source .venv/bin/activate
pip install -e .`)}
          <p>Development tools, including pytest and Ruff:</p>
          ${code('pip install -e ".[dev]"')}
          <p>Or, with uv:</p>
          ${code("uv sync --group dev")}
        `,
      },
    ])}
    ${h2("confirm-it-started", "Confirm it started")}
    <p>After install, check the CLI before you ask it to change a repository:</p>
    ${steps([
      `Run ${c("pari-cli --version")} and confirm the command is on your PATH.`,
      `Change to the project you want PARI to edit.`,
      `Sign in with ${c("pari-cli login")}. Pick DeepSeek, OpenAI, Anthropic, Grok, or OpenRouter.`,
      `Run ${c("pari-cli --dry-run")}. On Linux this checks the workspace, Bubblewrap, and the model, and it does not start a turn.`,
      `Run ${c("pari-cli")} and ask for a change in that repository.`,
    ])}
    ${code(`cd ~/projects/my-app
pari-cli login
pari-cli --dry-run
pari-cli`)}
    <p>A passing dry run prints the workspace path, the sandbox mode, the model, and ${c("Self-check passed.")} Leave the terminal open while you use the session. Type ${c("/exit")} or press Ctrl+C to stop.</p>
    ${h2("run-pari-again", "Run PARI again")}
    <p>After you close the terminal, start PARI with the same command. The saved sign-in in ${c("~/.pari/auth.json")} is reused until you log out. Project history stays in that project’s ${c(".pari/")} directory.</p>
    ${tabs([
      {
        title: "curl",
        body: code("pari-cli"),
      },
      {
        title: "pipx",
        body: code("pari-cli"),
      },
      {
        title: "uv",
        body: code("pari-cli"),
      },
      {
        title: "From source",
        body: code(`cd pari
source .venv/bin/activate
pari-cli`),
      },
    ])}
    ${h2("common-startup-options", "Common startup options")}
    ${table(
      ["Option", "Description"],
      [
        [
          c("-w, --workspace <dir>"),
          "Project directory. The default is the current directory.",
        ],
        [
          c("--model <name>"),
          `Model id. The default is ${c("PARI_MODEL")}, then the latest saved sign-in.`,
        ],
        [
          c("--sandbox <mode>"),
          `${c("auto")} or ${c("bwrap")} uses Bubblewrap on Linux. ${c("seatbelt")}, ${c("cloud")}, and ${c("none")} are not available yet.`,
        ],
        [
          c("--add <file>"),
          "Pin a file into the session. Repeat the flag for another file. The file must already exist inside the workspace.",
        ],
        [
          c("--edit-fallback <mode>"),
          `${c("none")} keeps exact edits. ${c("cascade")} allows the fallback edit path. The default is ${c("none")}.`,
        ],
        [
          c("--repomap <mode>"),
          `${c("off")} uses search. ${c("ppr")} turns on the repository map. The default is ${c("off")}.`,
        ],
        [
          c("--dry-run"),
          "Check the workspace, sandbox, and model, then exit.",
        ],
        [c("-v, --version"), "Print the version."],
        [c("-h, --help"), "Show help."],
      ],
    )}
    <p>Open one project and pin a file before the prompt:</p>
    ${code("pari-cli --workspace ~/projects/my-app --add README.md")}
    <p>These subcommands do not start a conversation:</p>
    ${table(
      ["Command", "Description"],
      [
        [c("pari-cli find [pattern]"), "List files matching a glob. The default pattern is *."],
        [
          c("pari-cli grep <query>"),
          `Search file contents. Add ${c("--regex")} to treat the query as a regular expression.`,
        ],
        [c("pari-cli login"), "Save an API key or an account token."],
        [c("pari-cli logout"), "Remove a saved sign-in."],
        [
          c("pari-cli eval"),
          "Reserved for benchmark suites. The harness is not available yet, and the command exits with an error.",
        ],
      ],
    )}
    ${h2("environment-variables", "Environment variables")}
    ${table(
      ["Variable", "Purpose"],
      [
        [
          c("PARI_MODEL"),
          "Model id used when --model is omitted. This wins over the latest saved sign-in.",
        ],
        [
          c("PARI_SANDBOX"),
          `Sandbox mode when --sandbox is omitted. ${c("PARI_SANDBOX_MODE")} is accepted as the same setting.`,
        ],
        [
          c("PARI_AUTH_FILE"),
          `Path of the sign-in file. The default is ${c("~/.pari/auth.json")}.`,
        ],
        [c("OPENAI_API_KEY"), "OpenAI key. An environment key is used before the saved sign-in."],
        [c("ANTHROPIC_API_KEY"), "Anthropic key."],
        [c("DEEPSEEK_API_KEY"), "DeepSeek key."],
        [c("XAI_API_KEY"), "Grok key."],
        [c("OPENROUTER_API_KEY"), "OpenRouter key."],
      ],
    )}
    <p>Example:</p>
    ${code(`export PARI_MODEL="deepseek-chat"
export DEEPSEEK_API_KEY="sk-..."
pari-cli`)}
    ${h2("stop-pari", "Stop PARI")}
    ${tabs([
      {
        title: "Session",
        body: `
          <p>At the prompt, type ${c("/exit")} or ${c("/quit")}. From the terminal that is running PARI, press Ctrl+C.</p>
        `,
      },
      {
        title: "A running command",
        body: `
          <p>A command the agent starts is killed when it hits its timeout. Closing the session also stops the sandboxed process group. You do not need a separate service to shut down.</p>
        `,
      },
    ])}
    ${h2("update-pari", "Update PARI")}
    <p>Settings and conversation files are outside the package. Upgrading the CLI leaves ${c("~/.pari/auth.json")} and each project’s ${c(".pari/")} directory in place.</p>
    ${tabs([
      {
        title: "curl",
        body: code("curl -fsSL https://pari-cli.in/install.sh | bash"),
      },
      {
        title: "pipx",
        body: code("pipx upgrade pari-cli"),
      },
      {
        title: "uv",
        body: code("uv tool upgrade pari-cli"),
      },
      {
        title: "pip",
        body: code("pip install --upgrade pari-cli"),
      },
    ])}
    ${h2("uninstall-pari", "Uninstall PARI")}
    ${tabs([
      {
        title: "pipx",
        body: code("pipx uninstall pari-cli"),
      },
      {
        title: "uv",
        body: code("uv tool uninstall pari-cli"),
      },
      {
        title: "pip",
        body: code("pip uninstall pari-cli"),
      },
      {
        title: "Installer venv",
        body: `
          <p>If the curl or PowerShell installer created ${c("~/.pari/venv")}, remove that directory. This also deletes ${c("~/.pari/auth.json")} when it lives in the same folder. Copy the auth file first if you still want the saved sign-in.</p>
          ${code("rm -rf ~/.pari")}
          <p>On Windows PowerShell:</p>
          ${code('Remove-Item -Recurse -Force "$env:USERPROFILE\\.pari"')}
        `,
      },
    ])}
    <p>Removing the package does not delete ${c(".pari/")} folders inside your projects. Delete those yourself if you also want the session logs gone.</p>
    ${callout(
      "note",
      `<p>If the CLI is missing, a dry run fails, or a model will not answer, use <a href="/docs/troubleshooting">Troubleshooting</a>.</p>`,
    )}
    ${h2("next", "Next")}
    ${next([
      {
        href: "/docs/first-session",
        title: "First session",
        text: "Sign in, open a workspace, and start a conversation.",
      },
      {
        href: "/docs/models",
        title: "Models",
        text: "Choose a provider and switch models inside a session.",
      },
      {
        href: "/docs/sandbox",
        title: "Sandbox",
        text: "See what a command can read, write, and reach on the network.",
      },
    ])}
  `;
}

function firstSession(): string {
  beginDocument();
  return `
    <p class="lede">Sign in, open the repository you want changed, and ask PARI to do the work.</p>
    ${h2("sign-in", "Sign in")}
    <p>From any directory:</p>
    ${code("pari-cli login")}
    <p>The menu asks for a provider, then an API key or an account token. DeepSeek accepts an API key only. You can also pass the credential without the menu:</p>
    ${code("pari-cli login deepseek --api-key sk-...")}
    <p>The secret is written to ${c("~/.pari/auth.json")} and is not copied into the sandbox. See <a href="/docs/models">Models</a> for every provider.</p>
    ${h2("open-a-workspace", "Open a workspace")}
    <p>PARI edits the directory you start it in. Move there first, or pass ${c("--workspace")}.</p>
    ${code(`cd ~/projects/my-app
pari-cli --dry-run`)}
    <p>On Linux, a good dry run looks like this:</p>
    ${code(`PARI v0.1.7 — Terminal Coding Agent (https://pari-cli.in)
Workspace: /home/you/projects/my-app
Sandbox: auto
Model: deepseek-chat
Self-check passed.`)}
    <p>If the workspace path is wrong, stop and start again in the right directory. Files outside that directory cannot be pinned or edited.</p>
    ${h2("start-a-conversation", "Start a conversation")}
    ${code("pari-cli")}
    <p>At the prompt, describe the outcome you want. For example:</p>
    ${code("Fix the failing test in tests/test_api.py and update the README.")}
    <p>PARI searches, edits, and, on Linux, runs commands such as the test runner. When it finishes a step, look at what changed before you ask for the next thing.</p>
    ${h2("review-the-change", "Review the change")}
    ${table(
      ["At the prompt", "What it does"],
      [
        [c("/diff"), "Show the uncommitted diff in the workspace."],
        [c("/undo"), "Revert files changed by the latest turn."],
        [c("/add README.md"), "Pin a file so the next turn keeps it in context."],
        [c("/cost"), "Show token and cost totals for this session."],
        [c("/exit"), "Leave the session. The project log stays on disk."],
      ],
    )}
    <p>The rest of the slash commands are on the <a href="/docs/commands">Commands</a> page.</p>
    ${h2("run-it-again", "Run it again")}
    <p>Next time, the same two commands are enough if you are still signed in:</p>
    ${code(`cd ~/projects/my-app
pari-cli`)}
    ${callout(
      "note",
      `<p>${c("/reset")} clears the conversation and keeps the session root. It does not revert files. Use ${c("/undo")} for the last file change, and git when you want to discard the whole working tree.</p>`,
    )}
    ${h2("next", "Next")}
    ${next([
      {
        href: "/docs/commands",
        title: "Commands",
        text: "Flags, search subcommands, and every slash command.",
      },
      {
        href: "/docs/sandbox",
        title: "Sandbox",
        text: "What those shell commands are allowed to touch.",
      },
    ])}
  `;
}

function commands(): string {
  beginDocument();
  return `
    <p class="lede">Use the shell command to start PARI, and slash commands inside the prompt to inspect or steer the session.</p>
    ${h2("start-the-cli", "Start the CLI")}
    ${code("pari-cli --help")}
    ${table(
      ["Invocation", "When to use it"],
      [
        [c("pari-cli"), "Interactive session in the current directory."],
        [c("pari-cli --workspace <dir>"), "Interactive session in another directory."],
        [c("pari-cli --model <name>"), "Start on a specific model id."],
        [c("pari-cli --dry-run"), "Check the workspace, sandbox, and model."],
        [c("pari-cli --add <file>"), "Pin a workspace file before the first turn."],
        [c("pari-cli find <glob>"), "Find files without starting a session."],
        [c("pari-cli grep <text>"), "Search file contents without starting a session."],
        [c("pari-cli login"), "Save a provider credential."],
        [c("pari-cli logout [provider]"), "Remove one saved sign-in, or open the picker."],
      ],
    )}
    <p>Search examples:</p>
    ${code(`pari-cli find "src/**/*.py"
pari-cli grep "def load_config" --filter "*.py"`)}
    <p>${c("find")} and ${c("grep")} read the workspace as the CLI user. They do not go through Bubblewrap. Limits default to 100 paths and 50 matches. Raise them with ${c("--limit")}.</p>
    ${h2("inside-the-session", "Inside the session")}
    <p>Type ${c("/help")} at the prompt. A line that starts with ${c("/")} is handled locally and is not sent to the model.</p>
    ${table(
      ["Command", "Description"],
      [
        [c("/help"), "List the slash commands."],
        [c("/diff"), "Print the uncommitted unified diff."],
        [c("/undo"), "Revert files from the most recent turn."],
        [c("/model"), "Show the active model."],
        [c("/model <name>"), "Switch model. The previous model stays if the new name cannot be used."],
        [c("/add <file>"), "Pin a file that exists inside the workspace."],
        [c("/snapshot [name]"), "Save a named marker on the session log. This does not copy the files."],
        [c("/cost"), "Show token and cost totals."],
        [c("/reset"), "Clear the conversation and start a new session id. Pinned files stay."],
        [c("/login"), "Open the sign-in menu."],
        [c("/logout [provider]"), "Remove a saved sign-in."],
        [c("/clear"), "Clear the terminal screen."],
        [c("/exit"), "End the session. /quit does the same."],
      ],
    )}
    ${h2("a-short-session", "A short session")}
    <p>Pin a file, start the prompt, and describe the change. Then inspect it:</p>
    ${code(`pari-cli --add src/app.py`)}
    <p>At the prompt, ask for the fix. When the turn finishes:</p>
    ${code(`/diff
/undo
/exit`)}
    ${callout(
      "note",
      `<p>${c("/snapshot")} records a name in the session log. It is not a git commit and it does not restore files by itself. Use ${c("/undo")} to revert the last turn, or git to restore an older tree.</p>`,
    )}
    ${h2("next", "Next")}
    ${next([
      {
        href: "/docs/models",
        title: "Models",
        text: "Sign in and switch the model that answers the next turn.",
      },
      {
        href: "/docs/sandbox",
        title: "Sandbox",
        text: "How bash commands are contained.",
      },
    ])}
  `;
}

function models(): string {
  beginDocument();
  return `
    <p class="lede">PARI calls the provider you sign in to. There is no separate hosted model.</p>
    ${h2("providers", "Providers")}
    ${table(
      ["Provider", "Default model", "Environment variable", "Sign in"],
      [
        [
          "OpenAI",
          c("gpt-4o"),
          c("OPENAI_API_KEY"),
          c("pari-cli login openai --api-key <key>"),
        ],
        [
          "DeepSeek",
          c("deepseek-chat"),
          c("DEEPSEEK_API_KEY"),
          c("pari-cli login deepseek --api-key <key>"),
        ],
        [
          "Anthropic",
          c("claude-3-7-sonnet-20250219"),
          c("ANTHROPIC_API_KEY"),
          c("pari-cli login anthropic --api-key <key>"),
        ],
        [
          "Grok",
          c("grok-3"),
          c("XAI_API_KEY"),
          c("pari-cli login grok --api-key <key>"),
        ],
        [
          "OpenRouter",
          c("openrouter/openai/gpt-4o-mini"),
          c("OPENROUTER_API_KEY"),
          c("pari-cli login openrouter --api-key <key>"),
        ],
      ],
    )}
    <p>OpenAI, Anthropic, Grok, and OpenRouter also accept ${c("--account <token>")}. DeepSeek does not. An interactive terminal can use ${c("pari-cli login")} with no flags and pick from the menu.</p>
    ${h2("which-credential-is-used", "Which credential is used")}
    ${steps([
      `If ${c("--model")} was passed, that id selects the provider.`,
      `Otherwise ${c("PARI_MODEL")} selects it.`,
      "Otherwise the latest saved sign-in is used.",
      "Otherwise an API key already exported in the environment selects that provider’s default model.",
      "For a chosen provider, an environment key is sent before the saved sign-in.",
    ])}
    ${code(`export PARI_MODEL="claude-3-7-sonnet-20250219"
pari-cli`)}
    <p>Inside a session:</p>
    ${code(`/model
/model gpt-4o`)}
    ${h2("offline-model", "Offline model")}
    <p>${c("--model pari-core")} selects a local mock provider. It does not call an API and it is there for development. A real task needs one of the providers above.</p>
    ${callout(
      "note",
      `<p>If startup says no model is selected, run ${c("pari-cli login")} or set ${c("PARI_MODEL")} and the matching API key. The key file is ${c("~/.pari/auth.json")}, mode 0600.</p>`,
    )}
    ${h2("sign-out", "Sign out")}
    ${code(`pari-cli logout deepseek
pari-cli logout`)}
    <p>Naming a provider removes that row. With no name, the terminal picker lists what is saved.</p>
    ${h2("next", "Next")}
    ${next([
      {
        href: "/docs/first-session",
        title: "First session",
        text: "Use the signed-in model on a repository.",
      },
      {
        href: "/docs/troubleshooting",
        title: "Troubleshooting",
        text: "Fix a rejected key or a missing provider.",
      },
    ])}
  `;
}

function sandbox(): string {
  beginDocument();
  return `
    <p class="lede">Shell commands the agent runs go through the sandbox. On Linux that sandbox is Bubblewrap. PARI does not fall back to running the command as you.</p>
    ${callout(
      "warning",
      `<p>File edits are written into the workspace you opened. The sandbox is the boundary for shell commands. Isolation is the kernel policy. There is no list of blocked command names. A <a href="/docs/permissions">permission</a> rule can refuse to start a command, or widen the network and <code>.git</code> for that command. The command that starts still runs inside Bubblewrap.</p>`,
    )}
    ${h2("linux-bubblewrap", "Linux Bubblewrap")}
    <p>${c("auto")} is the default. On Linux it selects Bubblewrap. If ${c("bwrap")} is not installed in ${c("/usr/bin")}, ${c("/usr/local/bin")}, or ${c("/bin")}, the command fails with an install hint. A ${c("bwrap")} binary checked into the repository is ignored.</p>
    ${table(
      ["Rule", "What it means"],
      [
        [
          "Writable mount",
          "The workspace is the only writable directory. System paths are read-only.",
        ],
        [
          "Git metadata",
          `${c(".git")} inside the workspace is read-only from the sandbox.`,
        ],
        [
          "Hidden credentials",
          `${c("~/.ssh")}, ${c("~/.aws")}, ${c("~/.gnupg")}, shell rc files, ${c(".netrc")}, and ${c(".git-credentials")} are masked when they would otherwise be visible.`,
        ],
        [
          "Host environment",
          `The sandbox starts from a clean environment. Variables whose names look like ${c("KEY")}, ${c("TOKEN")}, ${c("SECRET")}, or ${c("PASSWORD")} are not copied in.`,
        ],
        [
          "Network",
          "The host network is off unless the command is a single package install.",
        ],
        [
          "Time limit",
          "A command is killed when it exceeds its timeout. The result is marked timed out.",
        ],
      ],
    )}
    ${h2("package-installs", "Package installs")}
    <p>One package-install command may use the network. A chained command may not. ${c("pip install requests")} can reach the network. ${c("pip install requests; curl https://example.com")} cannot.</p>
    <p>The allowed tools are pip, pip3, npm, pnpm, yarn, cargo, poetry, and uv. The allowed subcommands are install, add, update, fetch, and sync. Other network, a writable ${c(".git")}, and secret directories wait for a <a href="/docs/permissions">permission</a> rule or a prompt.</p>
    ${h2("other-systems", "Other systems")}
    ${table(
      ["Mode", "Status"],
      [
        [c("auto"), "Bubblewrap on Linux. On any other OS, startup of a command reports that sandbox support is coming soon."],
        [c("bwrap"), "Bubblewrap. This is the Linux backend."],
        [c("seatbelt"), "macOS Seatbelt is not available yet."],
        [c("cloud"), "The E2B cloud sandbox is not available yet."],
        [c("none"), "Unsandboxed execution is not available. PARI will not run the command on the host."],
      ],
    )}
    <p>Set the mode for one launch with ${c("--sandbox bwrap")}, or for the shell with ${c("PARI_SANDBOX")}.</p>
    ${h2("check-before-a-task", "Check before a task")}
    ${code("pari-cli --dry-run")}
    <p>On Linux this resolves the sandbox before a turn starts. On macOS and native Windows the same command reports that the sandbox is not available, which is the expected result today.</p>
    ${h2("next", "Next")}
    ${next([
      {
        href: "/docs/permissions",
        title: "Permissions",
        text: "Built-in rules, rules you write, and the prompt when a command needs more.",
      },
      {
        href: "/docs/setup",
        title: "Install",
        text: "Install Bubblewrap and confirm the dry run.",
      },
      {
        href: "/docs/troubleshooting",
        title: "Troubleshooting",
        text: "Fix a missing bwrap binary or a refused command.",
      },
    ])}
  `;
}

function permissions(): string {
  beginDocument();
  return `
    <p class="lede">Ordinary work in the project runs without a prompt. A command that needs more than the built-in rules stops and asks, unless you have already written a rule for it.</p>
    ${callout(
      "note",
      `<p>The Linux sandbox already keeps the defaults below: writes stay in the workspace, the network is off except one package install, ${c(".git")} is read-only, and secret directories are masked. A missing rule never counts as yes. See <a href="/docs/sandbox">Sandbox</a> for the kernel boundary.</p>`,
    )}
    ${h2("built-in", "Built in")}
    <p>These rules ship with PARI. A line in a permission file overrides the matching row. A deny wins over an allow.</p>
    ${table(
      ["Rule", "Default", "How you override it"],
      [
        [
          "Read, search, and edit files inside the project",
          "Allow",
          `Add ${c("read-only")} to a permission file.`,
        ],
        [
          "Run a command inside the project, with no network",
          "Allow",
          "A deny rule for that command.",
        ],
        [
          "Network for one package install",
          "Allow",
          `Add ${c("deny package-network")}.`,
        ],
        [
          "Network for any other command",
          "Ask",
          "An allow rule or a deny rule for that command.",
        ],
        [
          `Writing ${c(".git")}, including commit, push, and reset`,
          "Ask",
          "An allow rule or a deny rule for that command.",
        ],
        [
          `${c("~/.ssh")}, ${c("~/.aws")}, ${c("~/.gnupg")}, and credential files`,
          "Deny",
          "An allow rule for that command.",
        ],
      ],
    )}
    <p>A package install is one of pip, pip3, npm, pnpm, yarn, cargo, poetry, or uv, with install, add, update, fetch, or sync. ${c("pip install requests; curl https://example.com")} is not a package install.</p>
    <p>An allow rule starts that command and widens only the grant it needs, such as the network or a writable ${c(".git")}. The command still runs inside Bubblewrap. Allowing ${c("git push")} does not allow ${c("curl")}.</p>
    ${h2("rules-you-write", "Rules you write")}
    <p>Put one rule per line in the project file, the home file, or both.</p>
    ${table(
      ["File", "Applies to"],
      [
        [c(".pari/permissions"), "This project only."],
        [c("~/.pari/permissions"), "Every project."],
      ],
    )}
    ${code(`allow bash git push
allow bash git commit
allow bash curl *
deny bash rm *
deny package-network
read-only`)}
    <p>${c("allow")} and ${c("deny")} name the tool, then the command. A trailing ${c("*")} matches the rest of the line. ${c("deny package-network")} turns off network for package installs. ${c("read-only")} refuses writes for the session. Blank lines and lines that start with ${c("#")} are ignored.</p>
    <p>If either file denies a command, PARI does not run it and does not ask. An allow in either file runs it. Otherwise the built-in default applies.</p>
    ${h2("the-prompt", "The prompt")}
    <p>When a tool needs access that no rule covers, PARI stops before the command runs:</p>
    ${code(`git push needs network and a git write

  once
  this repo
  no`)}
    ${table(
      ["Choice", "What happens"],
      [
        ["once", "Run this command only. The next matching command asks again."],
        [
          "this repo",
          `Append the allow line to ${c(".pari/permissions")} and run the command.`,
        ],
        ["no", "Skip the command. The same command asks again next time."],
      ],
    )}
    ${h2("how-pari-decides", "How PARI decides")}
    ${steps([
      "A deny rule in either permission file refuses the command. There is no prompt.",
      "An allow rule that matches the command runs it, with the sandbox grant that command needs.",
      "A built-in allow runs it with no prompt.",
      "Anything else opens the prompt. The choices are once, this repo, and no.",
    ])}
    ${h2("git-push", "git push")}
    <p>${c("git push")} is a command that needs the network and a writable ${c(".git")}. Both default to ask, so the first push opens the prompt. Choosing this repo saves:</p>
    ${code("allow bash git push")}
    <p>The next ${c("git push")} in that project uses the saved rule. ${c("git commit")} is a separate command and asks on its own until you allow it too.</p>
    <p>An approved git write gets your ${c("user.name")} and ${c("user.email")} from the host, so the commit has an author. An approved push, fetch, or pull also gets a GitHub token from ${c("GH_TOKEN")}, ${c("GITHUB_TOKEN")}, or ${c("gh auth token")}. The token is offered to ${c("https://github.com")} only, and only for that command. The prompt shows ${c("uses GitHub token")} when it applies.</p>
    ${h2("next", "Next")}
    ${next([
      {
        href: "/docs/sandbox",
        title: "Sandbox",
        text: "The kernel boundary a command stays inside after you allow it.",
      },
      {
        href: "/docs/troubleshooting",
        title: "Troubleshooting",
        text: "Fix a refused command or a missing Bubblewrap.",
      },
    ])}
  `;
}

function troubleshooting(): string {
  beginDocument();
  return `
    <p class="lede">Match the message you see to the check below. Fix that part and run the same command again.</p>
    ${h2("command-not-found", "pari-cli: command not found")}
    <p>The installer finished, and the shell has not picked up the new ${c("PATH")} entry.</p>
    ${steps([
      "Open a new terminal.",
      `Confirm ${c("~/.local/bin")} is on ${c("PATH")} for a curl install that used a virtualenv.`,
      `Run ${c("pari-cli --version")}.`,
    ])}
    <p>If you used pipx or uv, their own bin directory has to be on ${c("PATH")}. ${c("pipx ensurepath")} prints what to add.</p>
    ${h2("python-version", "Python 3.11 or newer is required")}
    ${code("python3 --version")}
    <p>Install a current Python from <a href="https://www.python.org/downloads/">python.org</a> or your distribution, then run the installer again. On Windows, ${c("py -3 --version")} should report 3.11 or newer. The Windows installer skips the Microsoft Store stub under WindowsApps.</p>
    ${h2("bubblewrap-missing", "bubblewrap is not installed")}
    <p>On Linux, install the distro package and check the binary. PARI does not use a copy that lives inside the project.</p>
    ${code(`sudo apt-get install bubblewrap
bwrap --version
pari-cli --dry-run`)}
    ${h2("sandbox-coming-soon", "Sandbox support is coming soon")}
    <p>You are not on Linux, or you selected ${c("seatbelt")}, ${c("cloud")}, or ${c("none")}. PARI will not run that command on the host. Use Linux, or Ubuntu on WSL2, and leave the sandbox on ${c("auto")}.</p>
    ${h2("no-model", "No model selected")}
    ${code(`pari-cli login
pari-cli --dry-run`)}
    <p>You can also export ${c("PARI_MODEL")} and the provider’s API key. Environment keys override the saved file. If the auth file is corrupt, the error names ${c("~/.pari/auth.json")}. Move that file aside and sign in again.</p>
    ${h2("unknown-provider-or-model", "Unknown provider or model")}
    <p>Provider ids are ${c("openai")}, ${c("deepseek")}, ${c("anthropic")}, ${c("grok")}, and ${c("openrouter")}. A model id has to match that provider’s prefix, such as ${c("claude-")} or ${c("gpt-")}. ${c("/model")} with a bad name leaves the current model in place.</p>
    ${h2("file-outside-workspace", "File is outside the workspace")}
    <p>${c("--add")} and ${c("/add")} only accept a file inside the directory PARI was started in. ${c("cd")} to the repository root, or pass ${c("--workspace")} with that root. A missing path is reported as file not found.</p>
    ${h2("dry-run-versus-the-session", "Dry run failed, or the session started and a command did not")}
    <p>${c("--dry-run")} checks the sandbox before a turn. Starting ${c("pari-cli")} checks the model first, and checks Bubblewrap when a command actually runs. If the prompt opened and a later command failed, read that command’s error. The usual cause on Linux is a missing ${c("bwrap")}. The usual cause elsewhere is that the sandbox backend is not available yet.</p>
    ${h2("next", "Next")}
    ${next([
      {
        href: "/docs/setup",
        title: "Install",
        text: "Repeat the install and the dry run from a clean shell.",
      },
      {
        href: "/docs/models",
        title: "Models",
        text: "Sign in again if the credential was removed.",
      },
    ])}
  `;
}

const built: DocPage[] = [
  {
    slug: "",
    title: "PARI documentation",
    description:
      "Learn how to install PARI, sign in, and use it on a repository.",
    eyebrow: "Documentation",
    body: overview(),
  },
  {
    slug: "setup",
    title: "Install PARI",
    description: "Install, run, update, or uninstall PARI.",
    eyebrow: "Install",
    body: setup(),
  },
  {
    slug: "first-session",
    title: "First session",
    description: "Sign in, open a repository, and ask PARI to make a change.",
    eyebrow: "First session",
    body: firstSession(),
  },
  {
    slug: "commands",
    title: "Commands",
    description: "CLI flags, search subcommands, and in-session slash commands.",
    eyebrow: "Commands",
    body: commands(),
  },
  {
    slug: "models",
    title: "Models",
    description:
      "Sign in to DeepSeek, OpenAI, Anthropic, Grok, or OpenRouter.",
    eyebrow: "Models",
    body: models(),
  },
  {
    slug: "sandbox",
    title: "Sandbox",
    description: "What a PARI shell command can read, write, and reach.",
    eyebrow: "Sandbox",
    body: sandbox(),
  },
  {
    slug: "permissions",
    title: "Permissions",
    description:
      "Built-in permission rules, rules you write, and the prompt when a command needs more.",
    eyebrow: "Permissions",
    body: permissions(),
  },
  {
    slug: "troubleshooting",
    title: "Troubleshooting",
    description: "Fix install, sandbox, sign-in, and workspace errors.",
    eyebrow: "Troubleshooting",
    body: troubleshooting(),
  },
];

export const pages = new Map(built.map((page) => [page.slug, page]));
