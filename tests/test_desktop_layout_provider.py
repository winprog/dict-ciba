"""DesktopLayoutProvider 的单元测试。

桌面布局信息通过调用 `wmctrl -d` 获取，其输出格式在不同合成器下不同：
- GNOME workspace：`VP:` 为 `N/A` 或 `00`（不可用），DG 为单一屏幕尺寸；
- KDE 老式 viewport：`VP:` 为 `x,y` 逗号偏移，DG 为总工作区尺寸。

Adapter 把脆弱的 wmctrl 工具链解析成稳定的 DesktopLayout，测试喂罐装
文本（fake 掉实际子进程）验证解析正确性。
"""
from types import SimpleNamespace

from desktop_placement import DesktopLayout, DesktopLayoutProvider

# 真实 GNOME 50.1 系统的 wmctrl -d 输出（当前活跃桌面为 1，`*` 标记）
GNOME_WMCTRL_OUT = """\
0  - DG: 3840x2160  VP: N/A  WA: 13464 3706x2096  Workspace 1
1  * DG: 3840x2160  VP: 00  WA: 13464 3706x2096  Workspace 2
2  - DG: 3840x2160  VP: N/A  WA: 13464 3706x2096  
3  - DG: 3840x2160  VP: N/A  WA: 13464 3706x2096  N/A
4  - DG: 3840x2160  VP: N/A  WA: 13464 3706x2096  N/A
5  - DG: 3840x2160  VP: N/A  WA: 13464 3706x2096  N/A
6  - DG: 3840x2160  VP: N/A  WA: 13464 3706x2096  N/A
"""

# 老式 viewport 模型（KDE 风格）：每个桌面 VP 有逗号偏移
VIRTUAL_VIEWPORT_WMCTRL_OUT = """\
0  - DG: 7680x2160  VP: 0,0  WA: 0,0 7680,2160  kDesktop 1
1  * DG: 7680x2160  VP: 3840,0  WA: 3840,0 7680,2160  kDesktop 2
2  - DG: 7680x2160  VP: 7680,0  WA: 7680,0 7680,2160  kDesktop 3
"""


def test_parse_gnome_workspace_output():
    """GNOME 输出：VP 不可用解析为 (0,0)，DG 为屏幕尺寸，`*` 标记当前桌面。"""
    layout = DesktopLayoutProvider.parse(GNOME_WMCTRL_OUT)
    assert layout.current_desktop == 1
    assert (layout.viewport_width, layout.viewport_height) == (3840, 2160)
    assert [num for num, _, _ in layout.desktops] == list(range(7))
    # 所有桌面 VP 都被规约为 (0,0) -> 才会被判定为 workspace 模型
    assert all(vp_x == 0 and vp_y == 0 for _, vp_x, vp_y in layout.desktops)


def test_parse_viewport_output_with_vp_offsets():
    """viewport 输出：正确解析每行的 VP 逗号偏移。"""
    layout = DesktopLayoutProvider.parse(VIRTUAL_VIEWPORT_WMCTRL_OUT)
    assert layout.current_desktop == 1
    assert layout.desktops == ((0, 0, 0), (1, 3840, 0), (2, 7680, 0))


def test_parse_missing_current_returns_none():
    """没有 `*` 标记当前桌面时返回 None。"""
    out = "0  - DG: 3840x2160  VP: N/A  WA: 0,0 0,0  Workspace\n"
    assert DesktopLayoutProvider.parse(out) is None


def test_get_layout_uses_injected_runner():
    """get_layout 通过注入的 runner 获取 wmctrl 输出并解析。"""
    calls = []

    def fake_run():
        calls.append(1)
        return SimpleNamespace(returncode=0, stdout=GNOME_WMCTRL_OUT)

    provider = DesktopLayoutProvider(run_command=fake_run)
    layout = provider.get_layout()
    assert len(calls) == 1
    assert isinstance(layout, DesktopLayout)
    assert layout.current_desktop == 1


def test_get_layout_returns_none_on_nonzero_exit():
    provider = DesktopLayoutProvider(
        run_command=lambda: SimpleNamespace(returncode=1, stdout="")
    )
    assert provider.get_layout() is None