""""远离取词点"放置策略的单元测试。

取词时鼠标周围通常是正在阅读的文档，翻译窗口若贴近鼠标会遮挡内容。
该策略把窗口放到离取词点最远的屏幕象限，只用一个 margin 保证不贴屏边。
"""
from services.desktop_placement import (
    DesktopLayout,
    DesktopResolver,
    PlacementInput,
    WindowPlacement,
    WindowPlacementService,
)


def _workspace_layout(current=2, vw=3840, vh=2160):
    return DesktopLayout(
        current_desktop=current,
        viewport_width=vw,
        viewport_height=vh,
        desktops=tuple((i, 0, 0) for i in range(6)),
    )


def _service():
    return WindowPlacementService(resolver=DesktopResolver())


def _inp(mouse_x, mouse_y, w=800, h=600, layout=None):
    if layout is None:
        layout = _workspace_layout()
    return PlacementInput(
        layout=layout, mouse_x=mouse_x, mouse_y=mouse_y,
        window_width=w, window_height=h, fallback_screen=(3840, 2160),
    )


def test_avoid_places_window_far_upper_left():
    """鼠标在右下象限时，窗口落到左上角区域。"""
    r = _service().avoid_mouse(_inp(mouse_x=3000, mouse_y=1800))
    assert isinstance(r, WindowPlacement)
    assert r.desktop == 2
    assert (r.x, r.y) == (20, 20)  # (0,0) + margin


def test_avoid_top_left_mouse_goes_bottom_right():
    """鼠标在左上象限时，窗口落到右下角区域。"""
    r = _service().avoid_mouse(_inp(mouse_x=500, mouse_y=400))
    assert (r.x, r.y) == (3840 - 800 - 20, 2160 - 600 - 20)  # (3020, 1540)


def test_avoid_top_right_mouse_goes_bottom_left():
    """鼠标在右上象限时，窗口落到左下角区域。"""
    r = _service().avoid_mouse(_inp(mouse_x=3400, mouse_y=400))
    assert (r.x, r.y) == (20, 2160 - 600 - 20)  # (20, 1540)


def test_avoid_bottom_left_mouse_goes_top_right():
    """鼠标在左下象限时，窗口落到右上角区域。"""
    r = _service().avoid_mouse(_inp(mouse_x=500, mouse_y=1800))
    assert (r.x, r.y) == (3840 - 800 - 20, 20)  # (3020, 20)


def test_avoid_windows_wider_than_screen_clamped_into_view():
    """窗口比屏幕还大时，无论如何都裁剪回可视区域。"""
    r = _service().avoid_mouse(_inp(mouse_x=3400, mouse_y=400, w=4000, h=2200))
    assert r.x == 20
    assert r.y == 20


def test_avoid_retains_sticky_desktop():
    """避开取词点仍解析桌面，以便触发 window sticky。"""
    r = _service().avoid_mouse(_inp(mouse_x=3000, mouse_y=1800))
    assert r.desktop == 2