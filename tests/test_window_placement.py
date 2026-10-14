"""WindowPlacementService（Facade）的单元测试。

Facade 把"解析布局 -> 判桌面 -> 算窗口几何"串成单个入口。这里的纯几何计算
（窗口置于鼠标上方/下方/角落、边界裁剪、无鼠标兜底）用已知字面量断言。
"""
from services.desktop_placement import (
    DesktopLayout,
    DesktopResolver,
    PlacementInput,
    WindowPlacement,
    WindowPlacementService,
)


def _workspace_layout(current, num_desktops=6, vw=3840, vh=2160):
    return DesktopLayout(
        current_desktop=current,
        viewport_width=vw,
        viewport_height=vh,
        desktops=tuple((i, 0, 0) for i in range(num_desktops)),
    )


def _service():
    return WindowPlacementService(resolver=DesktopResolver())


def test_window_above_mouse_when_room_is_available():
    """鼠标上方有足够空间时，窗口置于鼠标上方且水平居中。"""
    layout = _workspace_layout(current=2)
    inp = PlacementInput(
        layout=layout, mouse_x=2000, mouse_y=1500,
        window_width=800, window_height=600, fallback_screen=(3840, 2160),
    )
    r = _service().compute(inp)
    assert r.desktop == 2
    assert (r.x, r.y) == (1600, 870)  # 1500-600-30=870, 2000-400=1600


def test_window_below_mouse_near_top():
    """鼠标靠近屏幕顶部、上方放不下时，窗口置于鼠标下方。"""
    layout = _workspace_layout(current=0)
    inp = PlacementInput(
        layout=layout, mouse_x=2000, mouse_y=100,
        window_width=800, window_height=600, fallback_screen=(3840, 2160),
    )
    r = _service().compute(inp)
    assert (r.x, r.y) == (1600, 130)  # 100+30=130


def test_window_corner_when_no_room_above_or_below():
    """窗口比屏幕还高、上下都放不下时，落到左上角 margin 处。"""
    layout = _workspace_layout(current=0)
    inp = PlacementInput(
        layout=layout, mouse_x=400, mouse_y=500,
        window_width=800, window_height=2200, fallback_screen=(3840, 2160),
    )
    r = _service().compute(inp)
    assert (r.x, r.y) == (20, 20)


def test_window_x_clamped_to_screen_edge():
    """窗口右缘超出屏幕时被裁剪到屏幕边缘。"""
    layout = _workspace_layout(current=0)
    inp = PlacementInput(
        layout=layout, mouse_x=3800, mouse_y=1500,
        window_width=800, window_height=600, fallback_screen=(3840, 2160),
    )
    r = _service().compute(inp)
    # x=3400 但 3400+800>3840-20，故裁剪到 3840-800-20=3020
    assert (r.x, r.y) == (3020, 870)


def test_bottom_right_when_mouse_absent():
    """从未取词、无鼠标位置时，窗口置于右下角，无目标桌面。"""
    inp = PlacementInput(
        layout=None, mouse_x=None, mouse_y=None,
        window_width=800, window_height=600, fallback_screen=(1920, 1080),
    )
    r = _service().compute(inp)
    assert r.desktop is None
    assert (r.x, r.y) == (1070, 430)  # 1920-800-50, 1080-600-50


def test_layout_none_but_mouse_present_uses_absolute_coords():
    """有鼠标但布局缺失时，用绝对坐标做上/下定位，屏幕取兜底尺寸。"""
    inp = PlacementInput(
        layout=None, mouse_x=1000, mouse_y=1000,
        window_width=800, window_height=600, fallback_screen=(1920, 1080),
    )
    r = _service().compute(inp)
    assert r.desktop is None
    assert (r.x, r.y) == (600, 370)  # 1000-400, 1000-600-30


class _FakeProvider:
    def get_layout(self):
        return DesktopLayout(
            current_desktop=1, viewport_width=3840, viewport_height=2160,
            desktops=((0, 0, 0), (1, 0, 0)),
        )


def test_facade_chains_provider_and_resolver():
    """current_placement 经由注入的 provider 取布局，再解析出桌面与几何。"""
    svc = WindowPlacementService(provider=_FakeProvider(), resolver=DesktopResolver())
    r = svc.current_placement(
        mouse=(2000, 1500), window_width=800, window_height=600,
        fallback_screen=(3840, 2160),
    )
    assert isinstance(r, WindowPlacement)
    assert r.desktop == 1
    assert (r.x, r.y) == (1600, 870)