import subprocess
import sys

import pytest

import modelito.ollama_service as ms


def test_install_command_for_current_platform_unix():
    cmd, display = ms.install_command_for_current_platform(platform_name="linux")
    assert isinstance(cmd, list)
    assert "/bin/sh" in cmd or cmd[0].endswith("sh")
    assert "curl" in display or "install.sh" in display


def test_install_command_for_current_platform_windows():
    cmd, display = ms.install_command_for_current_platform(platform_name="win32")
    assert isinstance(cmd, list)
    assert any("powershell" in (p.lower() or "") for p in cmd)
    assert "install.ps1" in display


def test_install_ollama_brew_prefers_brew(monkeypatch):
    # Simulate platform darwin and brew install producing an ollama binary
    installed = {"ok": False}

    def fake_get_ollama_binary():
        return "/usr/local/bin/ollama" if installed["ok"] else None

    def fake_run(cmd, *a, **kw):
        # emulate brew install side-effect
        installed["ok"] = True
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(ms, "get_ollama_binary", fake_get_ollama_binary)
    monkeypatch.setattr(ms.subprocess, "run", fake_run)
    # patch sys.platform to darwin for the duration
    monkeypatch.setattr(sys, "platform", "darwin", raising=False)

    ok = ms.install_ollama(allow_install=True, method="brew", timeout=5.0)
    assert ok is True


def test_install_ollama_script_fallback(monkeypatch):
    # Simulate no ollama binary initially and script install succeeding
    installed = {"ok": False}

    def fake_get_ollama_binary():
        return "/usr/local/bin/ollama" if installed["ok"] else None

    def fake_run(cmd, *a, **kw):
        installed["ok"] = True
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="script ran", stderr="")

    monkeypatch.setattr(ms, "get_ollama_binary", fake_get_ollama_binary)
    monkeypatch.setattr(ms.subprocess, "run", fake_run)
    monkeypatch.setattr(sys, "platform", "linux", raising=False)

    ok = ms.install_ollama(allow_install=True, method=None, timeout=5.0)
    assert ok is True


def test_install_service_returns_combined_output(monkeypatch):
    def fake_run(cmd, *a, **kw):
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="installed", stderr="")

    monkeypatch.setattr(ms.subprocess, "run", fake_run)
    rc, out = ms.install_service(reinstall=False)
    assert rc == 0
    assert "installed" in out
