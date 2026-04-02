#!/usr/bin/env python3
"""Unit tests for shield/file_guard.py."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import call, patch

import pytest

MODULE_PATH = Path(__file__).with_name("file_guard.py")
SPEC = spec_from_file_location("file_guard_under_test", MODULE_PATH)
file_guard = module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(file_guard)


def completed_process(returncode=0, stdout=""):
    return SimpleNamespace(returncode=returncode, stdout=stdout)


def test_expand_path_expands_user_and_resolves():
    resolved = Path("/resolved/file.txt")

    with (
        patch.object(file_guard.os.path, "expanduser", return_value="/expanded/file.txt") as expanduser_mock,
        patch.object(Path, "resolve", autospec=True, return_value=resolved) as resolve_mock,
    ):
        result = file_guard.expand_path("~/file.txt")

    assert result == resolved
    expanduser_mock.assert_called_once_with("~/file.txt")
    resolve_mock.assert_called_once()


@pytest.mark.parametrize(
    ("filepath", "expected"),
    [
        (Path("/virtual/agent.log"), True),
        (Path("/virtual/alerts/report.txt"), True),
        (Path("/virtual/__pycache__"), True),
        (Path("/virtual/source.py"), False),
    ],
)
def test_should_exclude_matches_expected_patterns(filepath, expected):
    assert file_guard.should_exclude(filepath) is expected


def test_collect_files_includes_single_file_when_allowed():
    target = Path("/virtual/config.py")

    with (
        patch.object(file_guard, "expand_path", return_value=target),
        patch.object(Path, "is_file", autospec=True, side_effect=lambda self: self == target),
        patch.object(Path, "is_dir", autospec=True, return_value=False),
    ):
        result = file_guard.collect_files(["~/config.py"])

    assert result == [target]


def test_collect_files_skips_excluded_names_and_excluded_patterns():
    named_skip = Path("/virtual/skip.py")
    json_skip = Path("/virtual/state.json")

    mapping = {
        "~/skip.py": named_skip,
        "~/state.json": json_skip,
    }

    with (
        patch.object(file_guard, "expand_path", side_effect=lambda raw: mapping[raw]),
        patch.object(Path, "is_file", autospec=True, return_value=True),
        patch.object(Path, "is_dir", autospec=True, return_value=False),
    ):
        result = file_guard.collect_files(
            ["~/skip.py", "~/state.json"],
            exclude_names=["skip.py"],
        )

    assert result == []


def test_collect_files_include_data_allows_json_files():
    target = Path("/virtual/state.json")

    with (
        patch.object(file_guard, "expand_path", return_value=target),
        patch.object(Path, "is_file", autospec=True, side_effect=lambda self: self == target),
        patch.object(Path, "is_dir", autospec=True, return_value=False),
    ):
        result = file_guard.collect_files(["~/state.json"], include_data=True)

    assert result == [target]


def test_collect_files_recurses_directories_deduplicates_and_sorts():
    root = Path("/virtual/root")
    alpha = root / "alpha.py"
    beta = root / "beta.py"
    skipped = root / "cache.json"

    def is_file(self):
        return self in {alpha, beta, skipped}

    def is_dir(self):
        return self == root

    def rglob(self, pattern):
        assert pattern == "*"
        if self == root:
            return [beta, alpha, alpha, skipped]
        return []

    with (
        patch.object(file_guard, "expand_path", side_effect=[root, root]),
        patch.object(Path, "is_file", autospec=True, side_effect=is_file),
        patch.object(Path, "is_dir", autospec=True, side_effect=is_dir),
        patch.object(Path, "rglob", autospec=True, side_effect=rglob),
    ):
        result = file_guard.collect_files(["~/root", "~/root"])

    assert result == [alpha, beta]


def test_get_status_reports_locked_group_with_sizes():
    protected = Path("/protected/a.py")
    manifest = {
        "shield": {
            "label": "Shield",
            "paths": ["~/shield"],
            "category": "core",
        }
    }
    sizes = {
        protected: 123,
    }

    with (
        patch.object(file_guard, "GUARD_MANIFEST", manifest),
        patch.object(file_guard, "collect_files", return_value=[protected]) as collect_mock,
        patch.object(file_guard, "is_locked", return_value=True),
        patch.object(Path, "exists", autospec=True, side_effect=lambda self: self in sizes),
        patch.object(Path, "stat", autospec=True, side_effect=lambda self: SimpleNamespace(st_size=sizes[self])),
    ):
        status = file_guard.get_status()

    collect_mock.assert_called_once_with(["~/shield"], include_data=False, exclude_names=None)
    assert status["shield"]["status"] == "locked"
    assert status["shield"]["total"] == 1
    assert status["shield"]["locked_count"] == 1
    assert status["shield"]["files"][0]["size"] == 123


def test_get_status_reports_partial_group_and_zero_size_for_missing_file():
    locked_file = Path("/guard/locked.py")
    missing_file = Path("/guard/missing.py")
    manifest = {
        "dashboard": {
            "label": "Dashboard",
            "paths": ["~/dashboard"],
            "category": "core",
        }
    }
    locked = {locked_file: True, missing_file: False}

    with (
        patch.object(file_guard, "GUARD_MANIFEST", manifest),
        patch.object(file_guard, "collect_files", return_value=[locked_file, missing_file]),
        patch.object(file_guard, "is_locked", side_effect=lambda path: locked[path]),
        patch.object(Path, "exists", autospec=True, side_effect=lambda self: self == locked_file),
        patch.object(Path, "stat", autospec=True, return_value=SimpleNamespace(st_size=42)),
    ):
        status = file_guard.get_status()

    assert status["dashboard"]["status"] == "partial"
    assert status["dashboard"]["locked_count"] == 1
    assert status["dashboard"]["files"][1]["size"] == 0


def test_get_status_reports_hook_guard_status():
    repo_a = Path("/repo/a")
    repo_b = Path("/repo/b")
    manifest = {
        "github_push": {
            "label": "GitHub Push Access",
            "paths": [],
            "category": "core",
            "hook_guard": True,
            "repos": ["~/repo-a", "~/repo-b"],
        }
    }
    expand_map = {
        "~/repo-a": repo_a,
        "~/repo-b": repo_b,
    }
    locked = {
        repo_a: True,
        repo_b: False,
    }

    with (
        patch.object(file_guard, "GUARD_MANIFEST", manifest),
        patch.object(file_guard, "expand_path", side_effect=lambda raw: expand_map[raw]),
        patch.object(file_guard, "is_hook_locked", side_effect=lambda repo: locked[repo]),
    ):
        status = file_guard.get_status()

    assert status["github_push"]["status"] == "partial"
    assert status["github_push"]["total"] == 2
    assert status["github_push"]["locked_count"] == 1


def test_sudo_chflags_uses_password_stdin_when_provided():
    result = completed_process(returncode=0)
    demo_path = "/virtual/demo.txt"
    password_value = "".join(["sec", "ret"])

    with patch.object(file_guard.subprocess, "run", return_value=result) as run_mock:
        ok = file_guard._sudo_chflags("schg", demo_path, password=password_value)

    assert ok is True
    run_mock.assert_called_once_with(
        ["sudo", "-S", "chflags", "schg", demo_path],
        input=f"{password_value}\n",
        capture_output=True,
        text=True,
        timeout=10,
    )


def test_sudo_chflags_omits_password_stdin_when_not_provided():
    result = completed_process(returncode=1)
    demo_path = "/virtual/demo.txt"

    with patch.object(file_guard.subprocess, "run", return_value=result) as run_mock:
        ok = file_guard._sudo_chflags("noschg", demo_path)

    assert ok is False
    run_mock.assert_called_once_with(
        ["sudo", "chflags", "noschg", demo_path],
        input=None,
        capture_output=True,
        text=True,
        timeout=10,
    )


def test_lock_file_returns_error_for_missing_path():
    target = Path("/virtual/missing.txt")

    with (
        patch.object(file_guard, "expand_path", return_value=target),
        patch.object(Path, "exists", autospec=True, return_value=False),
    ):
        result = file_guard.lock_file("~/missing.txt")

    assert result == {"error": "File not found: ~/missing.txt"}


def test_lock_file_locks_existing_path():
    target = Path("/virtual/file.txt")
    password_value = "".join(["p", "w"])

    with (
        patch.object(file_guard, "expand_path", return_value=target),
        patch.object(Path, "exists", autospec=True, return_value=True),
        patch.object(file_guard, "_sudo_chflags", return_value=True) as sudo_mock,
    ):
        result = file_guard.lock_file("~/file.txt", password=password_value)

    assert result == {"path": str(target), "locked": True}
    sudo_mock.assert_called_once_with("schg", str(target), password_value)


def test_lock_file_returns_root_required_error_on_failed_sudo():
    target = Path("/virtual/file.txt")

    with (
        patch.object(file_guard, "expand_path", return_value=target),
        patch.object(Path, "exists", autospec=True, return_value=True),
        patch.object(file_guard, "_sudo_chflags", return_value=False),
    ):
        result = file_guard.lock_file("~/file.txt")

    assert result == {"error": "sudo failed — root required"}


def test_unlock_file_returns_error_for_missing_path():
    target = Path("/virtual/missing.txt")

    with (
        patch.object(file_guard, "expand_path", return_value=target),
        patch.object(Path, "exists", autospec=True, return_value=False),
    ):
        result = file_guard.unlock_file("~/missing.txt")

    assert result == {"error": "File not found: ~/missing.txt"}


def test_unlock_file_unlocks_existing_path():
    target = Path("/virtual/file.txt")
    password_value = "".join(["p", "w"])

    with (
        patch.object(file_guard, "expand_path", return_value=target),
        patch.object(Path, "exists", autospec=True, return_value=True),
        patch.object(file_guard, "_sudo_chflags", return_value=True) as sudo_mock,
    ):
        result = file_guard.unlock_file("~/file.txt", password=password_value)

    assert result == {"path": str(target), "unlocked": True}
    sudo_mock.assert_called_once_with("noschg", str(target), password_value)


def test_unlock_file_returns_root_required_error_on_failed_sudo():
    target = Path("/virtual/file.txt")

    with (
        patch.object(file_guard, "expand_path", return_value=target),
        patch.object(Path, "exists", autospec=True, return_value=True),
        patch.object(file_guard, "_sudo_chflags", return_value=False),
    ):
        result = file_guard.unlock_file("~/file.txt")

    assert result == {"error": "sudo failed — root required"}


def test_lock_group_rejects_unknown_group():
    assert file_guard.lock_group("missing-group") == {"error": "Unknown group: missing-group"}


def test_lock_group_locks_all_files_in_regular_group():
    first = Path("/guard/one.py")
    second = Path("/guard/two.py")
    password_value = "".join(["p", "w"])
    manifest = {
        "shield": {
            "label": "Shield",
            "paths": ["~/shield"],
            "category": "core",
        }
    }

    with (
        patch.object(file_guard, "GUARD_MANIFEST", manifest),
        patch.object(file_guard, "collect_files", return_value=[first, second]),
        patch.object(file_guard, "_sudo_chflags", side_effect=[True, False]) as sudo_mock,
    ):
        result = file_guard.lock_group("shield", password=password_value)

    assert result == {
        "group": "shield",
        "results": [
            {"path": str(first), "locked": True},
            {"path": str(second), "locked": False, "error": "sudo failed"},
        ],
    }
    assert sudo_mock.call_args_list == [
        call("schg", str(first), password_value),
        call("schg", str(second), password_value),
    ]


def test_unlock_group_uses_hook_unlock_for_hook_guard_groups():
    repo = Path("/repo/project")
    manifest = {
        "github_push": {
            "label": "GitHub Push Access",
            "paths": [],
            "category": "core",
            "hook_guard": True,
            "repos": ["~/repo"],
        }
    }

    with (
        patch.object(file_guard, "GUARD_MANIFEST", manifest),
        patch.object(file_guard, "expand_path", return_value=repo),
        patch.object(
            file_guard, "unlock_hook", return_value={"path": str(repo / ".git/hooks/pre-push"), "unlocked": True}
        ) as unlock_mock,
    ):
        result = file_guard.unlock_group("github_push")

    assert result["group"] == "github_push"
    assert result["results"] == [{"path": str(repo / ".git/hooks/pre-push"), "unlocked": True}]
    unlock_mock.assert_called_once_with(repo)


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        (file_guard.PRE_PUSH_HOOK, True),
        ("#!/bin/sh\necho custom hook\n", False),
    ],
)
def test_is_hook_locked_checks_for_shield_signature(content, expected):
    repo = Path("/repo/project")
    hook = repo / ".git" / "hooks" / "pre-push"

    with (
        patch.object(Path, "exists", autospec=True, side_effect=lambda self: self == hook),
        patch.object(Path, "read_text", autospec=True, return_value=content),
    ):
        assert file_guard.is_hook_locked(repo) is expected


def test_lock_hook_backs_up_existing_non_shield_hook_and_rewrites_hook():
    repo = Path("/repo/project")
    hook = repo / ".git" / "hooks" / "pre-push"
    backup = hook.with_suffix(".pre-shield-backup")

    with (
        patch.object(Path, "exists", autospec=True, side_effect=lambda self: self == hook),
        patch.object(Path, "read_text", autospec=True, return_value="#!/bin/sh\necho custom\n"),
        patch.object(Path, "rename", autospec=True) as rename_mock,
        patch.object(Path, "write_text", autospec=True) as write_mock,
        patch.object(Path, "chmod", autospec=True) as chmod_mock,
    ):
        result = file_guard.lock_hook(repo)

    assert result == {"path": str(hook), "locked": True}
    rename_mock.assert_called_once_with(hook, backup)
    write_mock.assert_called_once_with(hook, file_guard.PRE_PUSH_HOOK)
    chmod_mock.assert_called_once_with(hook, 0o755)


def test_unlock_hook_restores_backup_when_present():
    repo = Path("/repo/project")
    hook = repo / ".git" / "hooks" / "pre-push"
    backup = hook.with_suffix(".pre-shield-backup")

    def exists(self):
        return self in {hook, backup}

    with (
        patch.object(Path, "exists", autospec=True, side_effect=exists),
        patch.object(Path, "read_text", autospec=True, return_value=file_guard.PRE_PUSH_HOOK),
        patch.object(Path, "unlink", autospec=True) as unlink_mock,
        patch.object(Path, "rename", autospec=True) as rename_mock,
    ):
        result = file_guard.unlock_hook(repo)

    assert result == {"path": str(hook), "unlocked": True}
    unlink_mock.assert_called_once_with(hook)
    rename_mock.assert_called_once_with(backup, hook)


def test_migrate_uchg_to_schg_summarizes_all_outcomes():
    already = Path("/guard/already.py")
    migrated = Path("/guard/migrated.py")
    newly_locked = Path("/guard/new.py")
    broken = Path("/guard/broken.py")
    manifest = {
        "shield": {
            "label": "Shield",
            "paths": ["~/shield"],
            "category": "core",
        },
        "github_push": {
            "label": "GitHub Push Access",
            "paths": [],
            "category": "core",
            "hook_guard": True,
            "repos": ["~/repo"],
        },
    }

    def run_side_effect(cmd, **kwargs):
        target = cmd[-1]
        if cmd[:2] == ["ls", "-lO"]:
            if target == str(already):
                return completed_process(stdout="-rw-r--r-- schg")
            if target == str(migrated):
                return completed_process(stdout="-rw-r--r-- uchg")
            if target in {str(newly_locked), str(broken)}:
                return completed_process(stdout="-rw-r--r--")
        if cmd == ["chflags", "nouchg", str(migrated)]:
            return completed_process()
        if cmd == ["chflags", "schg", str(migrated)]:
            return completed_process()
        if cmd == ["chflags", "schg", str(newly_locked)]:
            return completed_process()
        if cmd == ["chflags", "schg", str(broken)]:
            raise file_guard.subprocess.CalledProcessError(1, cmd, "permission denied")
        raise AssertionError(f"Unexpected subprocess call: {cmd}")

    with (
        patch.object(file_guard, "GUARD_MANIFEST", manifest),
        patch.object(file_guard, "collect_files", return_value=[already, migrated, newly_locked, broken]),
        patch.object(file_guard.subprocess, "run", side_effect=run_side_effect),
    ):
        result = file_guard.migrate_uchg_to_schg()

    assert result["migrated"] == 1
    assert result["already"] == 1
    assert result["new"] == 1
    assert result["errors"] == 1
    assert [entry["action"] for entry in result["details"]] == [
        "already_schg",
        "migrated",
        "locked_new",
        "error",
    ]
