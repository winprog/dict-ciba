"""audio_player.play_audio 的策略分支测试。

play_audio 在后台线程运行并调用模块级 subprocess/requests。测试用
monkeypatch 替换这两者，验证主播放链路、失败回退与缺播放器早退。
不触碰真实网络/音频。
"""
import time

import pytest

from services import audio_player


class FakeResult:
    def __init__(self, returncode, stderr=b""):
        self.returncode = returncode
        self.stderr = stderr


class FakeResponse:
    def __init__(self, content=b"data"):
        self.content = content

    def raise_for_status(self):
        return None


def wait_until(condition, timeout=2.0):
    deadline = time.time() + timeout
    while not condition() and time.time() < deadline:
        time.sleep(0.01)


def make_harness(monkeypatch, which_rc=0, ffplay_rc=0, ffplay_stderr=b""):
    calls = []
    get_calls = []

    def fake_run(args, **kw):
        calls.append(list(args))
        if args[0] == "which":
            return FakeResult(which_rc)
        return FakeResult(ffplay_rc, ffplay_stderr)

    def fake_get(url, **kw):
        get_calls.append(url)
        return FakeResponse()

    monkeypatch.setattr(audio_player.subprocess, "run", fake_run)
    monkeypatch.setattr(audio_player.requests, "get", fake_get)
    return calls, get_calls


def test_empty_url_does_not_spawn_anything(monkeypatch):
    calls, get_calls = make_harness(monkeypatch)
    audio_player.play_audio("")
    audio_player.play_audio(None)
    time.sleep(0.1)
    assert calls == []
    assert get_calls == []


def test_success_uses_ffplay_without_download(monkeypatch):
    calls, get_calls = make_harness(monkeypatch, which_rc=0, ffplay_rc=0)
    audio_player.play_audio("http://example.com/a.mp3")
    wait_until(lambda: len(calls) >= 2)

    assert calls[0] == ["which", "ffplay"]
    assert calls[1][0] == "ffplay"
    assert "http://example.com/a.mp3" in calls[1]        # 直接播 URL
    assert get_calls == []                               # 未走下载回退


def test_ffplay_failure_falls_back_to_download(monkeypatch):
    calls, get_calls = make_harness(
        monkeypatch, which_rc=0, ffplay_rc=1, ffplay_stderr=b"404 Not Found"
    )
    audio_player.play_audio("http://example.com/a.mp3")
    wait_until(lambda: get_calls)                        # 等待触发下载

    # 主 ffplay 失败 + 尚未成功，应出现第二次 ffplay（播放临时文件）
    wait_until(lambda: len([c for c in calls if c[0] == "ffplay"]) >= 2)
    assert get_calls == ["http://example.com/a.mp3"]
    assert len([c for c in calls if c[0] == "ffplay"]) == 2


def test_ffplay_missing_returns_without_download(monkeypatch):
    calls, get_calls = make_harness(monkeypatch, which_rc=1, ffplay_rc=0)
    audio_player.play_audio("http://example.com/a.mp3")
    time.sleep(0.2)

    assert calls == [["which", "ffplay"]]
    assert get_calls == []