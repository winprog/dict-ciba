"""DesktopResolver 的单元测试。

DesktopResolver 是全项目中"鼠标坐标 -> 桌面 + 相对坐标"的纯逻辑判定，与
GNOME/Wayland 解耦，是可测性最高的接缝。以下用已知正确的手算字面量作为
独立事实来源断言（避免自证）。

scenario 对应 GNOME workspace 模型（所有 VP 相同）与老式 viewport 模型
（每个桌面有不同 VP 偏移）。
"""
import pytest

from desktop_placement import DesktopLayout, DesktopResolver, Placement


def _workspace_layout(current, num_desktops=6, vw=3840, vh=2160):
    """构造 workspace 模型布局：所有桌面 VP=(0,0)，共享同一张 3840x2160 屏。"""
    return DesktopLayout(
        current_desktop=current,
        viewport_width=vw,
        viewport_height=vh,
        desktops=tuple((i, 0, 0) for i in range(num_desktops)),
    )


def test_workspace_model_returns_current_desktop_and_absolute_coords():
    """workspace 模型下：鼠标在哪个桌面取决于当前活跃桌面，坐标即屏幕绝对坐标。"""
    layout = _workspace_layout(current=2)
    result = DesktopResolver.resolve(layout, mouse_x=2000, mouse_y=1000)
    assert result == Placement(desktop=2, rel_x=2000, rel_y=1000)


def test_workspace_model_nonzero_current_desktop():
    """当前活跃桌面不是 0 时也能正确返回。"""
    layout = _workspace_layout(current=5)
    result = DesktopResolver.resolve(layout, mouse_x=10, mouse_y=20)
    assert result == Placement(desktop=5, rel_x=10, rel_y=20)


def test_viewport_model_finds_desktop_by_mouse_range():
    """viewport 模型下：鼠标落点要减去所在桌面的 VP 偏移，得到桌面内相对坐标。"""
    layout = DesktopLayout(
        current_desktop=0,
        viewport_width=3840,
        viewport_height=2160,
        desktops=((0, 0, 0), (1, 3840, 0), (2, 7680, 0)),
    )
    # 桌面1 的 VP=(3840,0)，鼠标绝对 (5000,1000) -> 相对 (1160,1000)
    result = DesktopResolver.resolve(layout, mouse_x=5000, mouse_y=1000)
    assert result == Placement(desktop=1, rel_x=1160, rel_y=1000)


def test_viewport_model_matches_second_viewport():
    """桌面2 的 VP=(7680,0)，鼠标绝对 (9000,500) -> 相对 (1320,500)。"""
    layout = DesktopLayout(
        current_desktop=2,
        viewport_width=3840,
        viewport_height=2160,
        desktops=((0, 0, 0), (1, 3840, 0), (2, 7680, 0)),
    )
    result = DesktopResolver.resolve(layout, mouse_x=9000, mouse_y=500)
    assert result == Placement(desktop=2, rel_x=1320, rel_y=500)


def test_viewport_model_no_match_falls_back_to_current_desktop():
    """鼠标落点不在任何桌面范围内时回退到当前桌面，并减去其 VP 偏移。"""
    layout = DesktopLayout(
        current_desktop=2,
        viewport_width=3840,
        viewport_height=2160,
        desktops=((0, 0, 0), (1, 3840, 0), (2, 7680, 0)),
    )
    # 桌面2 的 VP=(7680,0)，鼠标绝对 (20000,500) -> 相对 (12320,500)
    result = DesktopResolver.resolve(layout, mouse_x=20000, mouse_y=500)
    assert result == Placement(desktop=2, rel_x=12320, rel_y=500)