"""Sticky ClientMessage 构造的单元测试。

根因：GNOME 50.1 + Wayland 下，Mutter 不响应 xprop 改写 _NET_WM_DESKTOP
属性，只响应 _NET_WM_DESKTOP 的 ClientMessage 通知（source=1）。
本测试锁定 sticky 通知所需的窗口逻辑参数。
"""
from desktop_placement import (
    sticky_client_message_data,
    sticky_source_indication,
)


def test_sticky_data_is_all_desktops_hex():
    """sticky 的桌面 slot 应是 0xFFFFFFFF（全桌面）。"""
    data = sticky_client_message_data()
    assert data[0] == 0xFFFFFFFF


def test_sticky_data_source_indication_is_one():
    """source_indication=1：来自用户/pager 的申请，WM 才执行。"""
    data = sticky_client_message_data()
    assert data[1] == 1


def test_sticky_source_indication_constant():
    assert sticky_source_indication() == 1


def test_sticky_data_length_is_five():
    """_NET_WM_DESKTOP 的 data 是 5 个 long。"""
    assert len(sticky_client_message_data()) == 5