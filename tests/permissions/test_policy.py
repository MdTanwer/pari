"""Built-in rules, user rules, and the ask decision."""

from pathlib import Path

from pari.permissions.policy import Grants, PermissionPolicy, normalize_choice
from pari.sandbox.base import is_package_install


def _policy(tmp_path: Path, project: str = "", home: str = "") -> PermissionPolicy:
    root = tmp_path / "project"
    root.mkdir()
    house = tmp_path / "home"
    house.mkdir()
    if project:
        path = root / ".pari"
        path.mkdir()
        (path / "permissions").write_text(project)
    if home:
        path = house / ".pari"
        path.mkdir()
        (path / "permissions").write_text(home)
    return PermissionPolicy.load(root, home=house)


def test_ordinary_commands_run(tmp_path: Path):
    policy = _policy(tmp_path)
    for command in ("pytest -q", "git status", "git diff", "echo hello"):
        decision = policy.decide("bash", command)
        assert decision.action == "run", command
        assert decision.grants.any() is False


def test_git_list_forms_run_without_asking(tmp_path: Path):
    policy = _policy(tmp_path)
    for command in (
        "git status && git remote -v && git branch -vv",
        "git branch",
        "git branch --list 'feat/*'",
        "git tag",
        "git stash list",
        "git config --get user.name",
        "git remote get-url origin",
    ):
        decision = policy.decide("bash", command)
        assert decision.action == "run", command


def test_git_forms_that_change_the_repo_ask(tmp_path: Path):
    policy = _policy(tmp_path)
    for command in (
        "git branch feature",
        "git branch -D old",
        "git tag v1",
        "git remote add origin x",
        "git stash",
        "git config user.name me",
    ):
        decision = policy.decide("bash", command)
        assert decision.action == "ask", command
        assert decision.grants.git_write is True, command


def test_git_push_asks_for_network_and_git_write(tmp_path: Path):
    decision = _policy(tmp_path).decide("bash", "git push origin main")
    assert decision.action == "ask"
    assert decision.grants.network is True
    assert decision.grants.git_write is True
    assert decision.grants.secrets is False
    assert decision.grants.github_token is True
    assert decision.message == (
        "git push origin main needs network, a git write, and your GitHub token"
    )
    assert decision.save_line == "allow bash git push"


def test_git_commit_asks_only_for_git_write(tmp_path: Path):
    decision = _policy(tmp_path).decide("bash", "git commit -m hi")
    assert decision.action == "ask"
    assert decision.grants == Grants(git_write=True)
    assert decision.message == "git commit -m hi needs a git write"
    assert decision.save_line == "allow bash git commit"


def test_git_flag_before_subcommand_still_matches(tmp_path: Path):
    root = tmp_path / "project"
    root.mkdir()
    pari = root / ".pari"
    pari.mkdir()
    (pari / "permissions").write_text("allow bash git push\n")
    policy = PermissionPolicy.load(root, home=tmp_path / "home")
    decision = policy.decide("bash", "git -C other push origin main")
    assert decision.action == "run"
    assert decision.grants.network is True
    assert decision.grants.git_write is True


def test_ls_remote_needs_network_and_token_but_no_git_write(tmp_path: Path):
    decision = _policy(tmp_path).decide("bash", "git ls-remote --heads origin")
    assert decision.action == "ask"
    assert decision.grants == Grants(network=True, github_token=True)


def test_gh_asks_for_network_and_token(tmp_path: Path):
    policy = _policy(tmp_path)
    decision = policy.decide("bash", 'gh pr create --title "Fix" --body "Closes #3"')
    assert decision.action == "ask"
    assert decision.grants == Grants(network=True, github_token=True)
    assert decision.save_line == "allow bash gh pr create"
    view = policy.decide("bash", "gh issue view 3 --repo MdTanwer/pari 2>&1")
    assert view.action == "ask"
    assert view.grants.github_token is True
    assert policy.decide("bash", "gh help").action == "run"
    piped = policy.decide(
        "bash", "gh issue view 3 --repo MdTanwer/pari 2>&1 | head -60"
    )
    assert piped.action == "ask"
    assert piped.grants.github_token is True


def test_saved_gh_rule_covers_only_that_subcommand(tmp_path: Path):
    policy = _policy(tmp_path, project="allow bash gh pr create\n")
    created = policy.decide("bash", "gh pr create --fill")
    assert created.action == "run"
    assert created.grants.github_token is True
    assert policy.decide("bash", "gh pr merge 5").action == "ask"


def test_curl_asks_for_network(tmp_path: Path):
    decision = _policy(tmp_path).decide("bash", "curl https://example.com")
    assert decision.action == "ask"
    assert decision.message == "curl https://example.com needs network"
    assert decision.save_line == "allow bash curl *"


def test_package_install_runs_with_package_network(tmp_path: Path):
    decision = _policy(tmp_path).decide("bash", "pip install requests")
    assert decision.action == "run"
    assert decision.package_network is True
    assert decision.grants.network is False
    assert is_package_install("pip install requests") is True
    assert is_package_install("pip install requests; curl https://x") is False


def test_deny_package_network_leaves_the_command_offline(tmp_path: Path):
    policy = _policy(tmp_path, project="deny package-network\n")
    decision = policy.decide("bash", "pip install requests")
    assert decision.action == "run"
    assert decision.package_network is False


def test_deny_rule_skips_the_prompt(tmp_path: Path):
    policy = _policy(tmp_path, project="deny bash rm *\n")
    decision = policy.decide("bash", "rm -rf build")
    assert decision.action == "deny"
    assert decision.message == "Permission denied by a rule."


def test_allow_rule_runs_with_the_grant(tmp_path: Path):
    policy = _policy(tmp_path, project="allow bash git push\n")
    decision = policy.decide("bash", "git push")
    assert decision.action == "run"
    assert decision.grants.network is True
    assert decision.grants.git_write is True


def test_home_deny_beats_project_allow(tmp_path: Path):
    policy = _policy(
        tmp_path,
        project="allow bash git push\n",
        home="deny bash git push\n",
    )
    decision = policy.decide("bash", "git push origin main")
    assert decision.action == "deny"


def test_composed_push_is_not_covered_by_a_push_allow(tmp_path: Path):
    policy = _policy(tmp_path, project="allow bash git push\n")
    decision = policy.decide("bash", "git push && curl https://example.com")
    assert decision.action == "ask"
    assert decision.grants.network is True
    assert decision.grants.git_write is True


def test_cd_prefix_and_fd_redirect_still_ask(tmp_path: Path):
    policy = _policy(tmp_path)
    add = policy.decide(
        "bash",
        "cd /home/tanw9/pari && git add pari/fs/atomic.py 2>&1 | head -3",
    )
    assert add.action == "ask"
    assert add.grants.git_write is True
    create = policy.decide(
        "bash",
        "cd /home/tanw9/pari && gh pr create --repo MdTanwer/pari "
        '--base main --title "test" --body "test" 2>&1 | head -5',
    )
    assert create.action == "ask"
    assert create.grants.github_token is True
    assert create.grants.network is True
    checkout = policy.decide(
        "bash",
        "cd /home/tanw9/pari && git checkout -b test-branch-xyz 2>&1 | tail -3",
    )
    assert checkout.action == "ask"
    assert checkout.grants.git_write is True
    assert add.save_line == "allow bash git add"
    assert create.save_line == "allow bash gh pr create"


def test_saved_git_add_covers_a_cd_prefixed_command(tmp_path: Path):
    policy = _policy(tmp_path, project="allow bash git add\n")
    decision = policy.decide(
        "bash",
        "cd /home/tanw9/pari && git add pari/fs/atomic.py 2>&1 | head -3",
    )
    assert decision.action == "run"
    assert decision.grants.git_write is True


def test_touch_inside_git_asks_for_a_git_write(tmp_path: Path):
    decision = _policy(tmp_path).decide("bash", "touch .git/_writetest")
    assert decision.action == "ask"
    assert decision.grants.git_write is True


def test_widening_in_the_last_segment_still_asks(tmp_path: Path):
    policy = _policy(tmp_path)
    for command in (
        "git status && git push origin main",
        "echo hi; curl https://example.com",
        "ls | ssh host",
    ):
        decision = policy.decide("bash", command)
        assert decision.action == "ask", command
        assert decision.grants.network is True, command


def test_redirect_that_hides_curl_asks(tmp_path: Path):
    decision = _policy(tmp_path).decide("bash", "echo $(curl https://example.com)")
    assert decision.action == "ask"
    assert decision.grants.network is True


def test_plain_redirect_still_runs(tmp_path: Path):
    decision = _policy(tmp_path).decide("bash", "echo x > out.txt")
    assert decision.action == "run"
    assert decision.grants.any() is False


def test_ssh_asks_for_network_and_secrets(tmp_path: Path):
    decision = _policy(tmp_path).decide("bash", "ssh git@example.com")
    assert decision.action == "ask"
    assert decision.grants.network is True
    assert decision.grants.secrets is True
    assert "secret files" in decision.message


def test_reading_a_secret_path_asks(tmp_path: Path):
    decision = _policy(tmp_path).decide("bash", "cat .ssh/id_rsa")
    assert decision.action == "ask"
    assert decision.grants.secrets is True
    assert decision.grants.network is False


def test_read_only_refuses_a_git_write(tmp_path: Path):
    policy = _policy(tmp_path, project="read-only\nallow bash git commit\n")
    decision = policy.decide("bash", "git commit -m hi")
    assert decision.action == "deny"
    assert decision.message == "This session is read-only."
    assert decision.read_only is True


def test_comments_and_blank_lines_are_ignored(tmp_path: Path):
    policy = _policy(tmp_path, project="# note\n\nallow bash git push\n")
    assert policy.decide("bash", "git push").action == "run"


def test_this_repo_line_is_written_once(tmp_path: Path):
    root = tmp_path / "project"
    root.mkdir()
    policy = PermissionPolicy.load(root, home=tmp_path / "home")
    policy.save_project_rule("allow bash git push")
    policy.save_project_rule("allow bash git push")
    text = (root / ".pari" / "permissions").read_text()
    assert text == "allow bash git push\n"


def test_normalize_choice():
    assert normalize_choice("once") == "once"
    assert normalize_choice("this repo") == "repo"
    assert normalize_choice("NO") == "no"
    assert normalize_choice("yes") == "no"
