#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import tomllib
from pathlib import Path
from typing import Any


DEFAULT_PLUGIN_NAME = "openvault"
DEFAULT_MARKETPLACE = "totoro-local"
DEFAULT_BRANCH = "main"


def run_git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def git_rev_parse(repo: Path, ref: str) -> str:
    return run_git(repo, "rev-parse", ref)


def visible_skill_entries(repo_root: Path) -> list[str]:
    return sorted(path.relative_to(repo_root).as_posix() for path in repo_root.glob("skills/*/agents/openai.yaml"))


def plugin_key(plugin_name: str, marketplace: str) -> str:
    return f"{plugin_name}@{marketplace}"


def load_codex_config(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        return {}
    return tomllib.loads(config_path.read_text(encoding="utf-8"))


def plugin_enabled(config_path: Path, plugin_name: str, marketplace: str) -> bool:
    config = load_codex_config(config_path)
    plugins = config.get("plugins", {})
    plugin_cfg = plugins.get(plugin_key(plugin_name, marketplace), {})
    if not isinstance(plugin_cfg, dict):
        return False
    return bool(plugin_cfg.get("enabled", False))


def resolve_cache_repo(cache_root: Path, plugin_name: str, marketplace: str) -> Path:
    return cache_root.expanduser().resolve() / marketplace / plugin_name / "local"


def resolve_target_head(source_repo: Path, branch: str, commit: str | None = None) -> str:
    if commit:
        return git_rev_parse(source_repo, commit)
    run_git(source_repo, "fetch", "origin", branch)
    return git_rev_parse(source_repo, f"origin/{branch}")


def ensure_branch_checked_out(repo: Path, branch: str) -> None:
    result = subprocess.run(
        ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        run_git(repo, "switch", branch)
        return
    run_git(repo, "switch", "--track", "-c", branch, f"origin/{branch}")


def get_refresh_status(
    *,
    source_repo: Path,
    config_path: Path,
    cache_root: Path,
    plugin_name: str = DEFAULT_PLUGIN_NAME,
    marketplace: str = DEFAULT_MARKETPLACE,
    branch: str = DEFAULT_BRANCH,
    commit: str | None = None,
) -> dict[str, Any]:
    source_repo = source_repo.expanduser().resolve()
    config_path = config_path.expanduser().resolve()
    cache_repo = resolve_cache_repo(cache_root, plugin_name, marketplace)
    enabled = plugin_enabled(config_path, plugin_name, marketplace)
    if not cache_repo.exists():
        raise FileNotFoundError(f"cache clone not found: {cache_repo}")

    source_head = git_rev_parse(source_repo, "HEAD")
    cache_head = git_rev_parse(cache_repo, "HEAD")
    target_head = resolve_target_head(source_repo, branch, commit)
    visible_entries = visible_skill_entries(cache_repo)

    return {
        "plugin_enabled": enabled,
        "plugin_key": plugin_key(plugin_name, marketplace),
        "source_repo": str(source_repo),
        "config_path": str(config_path),
        "cache_repo": str(cache_repo),
        "source_head": source_head,
        "cache_head": cache_head,
        "target_head": target_head,
        "needs_refresh": cache_head != target_head,
        "visible_skill_count": len(visible_entries),
        "visible_skill_entries": visible_entries,
        "target_kind": "commit" if commit else "branch",
        "target_value": commit or branch,
    }


def refresh_cache_clone(
    *,
    source_repo: Path,
    config_path: Path,
    cache_root: Path,
    plugin_name: str = DEFAULT_PLUGIN_NAME,
    marketplace: str = DEFAULT_MARKETPLACE,
    branch: str = DEFAULT_BRANCH,
    commit: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    before = get_refresh_status(
        source_repo=source_repo,
        config_path=config_path,
        cache_root=cache_root,
        plugin_name=plugin_name,
        marketplace=marketplace,
        branch=branch,
        commit=commit,
    )
    result = {
        **before,
        "cache_head_before": before["cache_head"],
        "before_head": before["cache_head"],
        "after_head": before["cache_head"],
        "refreshed": False,
        "dry_run": dry_run,
    }

    if dry_run or not before["needs_refresh"]:
        return result

    cache_repo = Path(before["cache_repo"])
    run_git(cache_repo, "fetch", "origin")
    if commit:
        run_git(cache_repo, "switch", "--detach", commit)
    else:
        ensure_branch_checked_out(cache_repo, branch)
        run_git(cache_repo, "pull", "--ff-only", "origin", branch)

    after_head = git_rev_parse(cache_repo, "HEAD")
    visible_entries = visible_skill_entries(cache_repo)
    result.update(
        {
            "after_head": after_head,
            "cache_head": after_head,
            "needs_refresh": after_head != before["target_head"],
            "refreshed": after_head != before["cache_head"],
            "visible_skill_count": len(visible_entries),
            "visible_skill_entries": visible_entries,
        }
    )
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh the local Codex cache clone for openvault and report cache/source commit alignment.")
    parser.add_argument("--source-repo", default=str(Path(__file__).resolve().parents[1]), help="Path to the canonical openvault repository")
    parser.add_argument("--config-path", default=str(Path.home() / ".codex" / "config.toml"), help="Path to Codex config.toml")
    parser.add_argument("--cache-root", default=str(Path.home() / ".codex" / "plugins" / "cache"), help="Path to Codex plugin cache root")
    parser.add_argument("--plugin-name", default=DEFAULT_PLUGIN_NAME)
    parser.add_argument("--marketplace", default=DEFAULT_MARKETPLACE)
    parser.add_argument("--branch", default=DEFAULT_BRANCH, help="Branch to refresh the cache clone onto")
    parser.add_argument("--commit", help="Optional commit to refresh the cache clone onto instead of a branch tip")
    parser.add_argument("--dry-run", action="store_true", help="Report what would change without modifying the cache clone")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = refresh_cache_clone(
        source_repo=Path(args.source_repo),
        config_path=Path(args.config_path),
        cache_root=Path(args.cache_root),
        plugin_name=args.plugin_name,
        marketplace=args.marketplace,
        branch=args.branch,
        commit=args.commit,
        dry_run=args.dry_run,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
