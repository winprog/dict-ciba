"""Sticky（驻留所有桌面）判定的单元测试。

在 Wayland + XWayland 下，Mutter 不响应 xprop 把窗口"移动到指定桌面"
（改 _NET_WM_DESKTOP 属性只是写属性，不触发移窗）。可靠的方案是
Sticky：把 _NET_WM_DESKTOP 设为 -1（0xFFFFFFFF），窗口驻留所有桌面，
这样无论用户在哪个虚拟桌面取词，窗口都在那个桌面可见。

这里的纯逻辑把"window 摆放语义"和"真实桌面号"分离，便于判定何时该
用 sticky 值，以及 sticky 值对应的 X 语义。
"""
import pytest

from desktop_placement import (
    sticky_desktop_value,
    is_sticky_desktop,
    net_wm_desktop_literal,
)


def test_sticky_desktop_uses_negative_one():
    """sticky 语义对应的 X 值是 -1（0xFFFFFFFF）。"""
    assert sticky_desktop_value() == -1


def test_is_sticky_detects_minus_one_and_wide_unsigned():
    """xprop 读回的 -1 可能是 4294967295（0xFFFFFFFF），都要识别为 sticky。"""
    assert is_sticky_desktop(-1) is True
    assert is_sticky_desktop(4294967295) is True  # 0xFFFFFFFF


def test_is_sticky_false_for_normal_desktops():
    assert is_sticky_desktop(0) is False
    assert is_sticky_desktop(3) is False


def test_net_wm_desktop_literal_gives_signed_sticky():
    """写给 xprop 的 _NET_WM_DESKTOP 字面量：sticky 应用 '-1'。"""
    assert net_wm_desktop_literal(sticky=True) == "-1"


def test_net_wm_desktop_literal_gives_number_for_desktop():
    assert net_wm_desktop_literal(desktop=3) == "3"