"""桌面布局解析：把鼠标绝对坐标解析为"所在桌面 + 桌面内相对坐标"。

这是全项目唯一的纯逻辑判定，与 GNOME/Wayland 解耦，便于单元测试。

模型说明：
- GNOME workspace 模型：所有桌面共享同一块屏幕，VP（viewport 偏移）全为 (0,0)，
  鼠标在哪个桌面取决于"当前活跃桌面"。
- 老式 viewport 模型：每个桌面是总工作区里的一块，VP 表示其左上角偏移，
  鼠标落点由绝对坐标与各桌面 VP 范围匹配得到。
"""
import re
import subprocess
from dataclasses import dataclass

# wmctrl -d 的 DG 字段：总工作区尺寸
_DG_RE = re.compile(r"DG:\s+(\d+)x(\d+)")
# VP 字段可能是 "x,y"（KDE viewport）、"0,0"、"00" 或 "N/A"（GNOME）
_VP_RE = re.compile(r"VP:\s+(\d+)\s*[, ]?\s*(\d+)")


@dataclass(frozen=True)
class DesktopLayout:
    current_desktop: int
    viewport_width: int | None
    viewport_height: int | None
    # ((desktop_num, vp_x, vp_y), ...)
    desktops: tuple


@dataclass(frozen=True)
class Placement:
    desktop: int
    rel_x: int
    rel_y: int


class DesktopResolver:
    """将桌面布局 + 鼠标绝对坐标解析为目标桌面与桌面内相对坐标。"""

    @staticmethod
    def resolve(layout: DesktopLayout, mouse_x: int, mouse_y: int) -> Placement:
        unique_vps = {(vp_x, vp_y) for _, vp_x, vp_y in layout.desktops}

        # 所有桌面 VP 相同 -> GNOME workspace 模型
        if len(unique_vps) <= 1:
            return Placement(layout.current_desktop, mouse_x, mouse_y)

        # viewport 模型：匹配鼠标落在哪个桌面的 VP 范围
        vw, vh = layout.viewport_width, layout.viewport_height
        if vw is not None and vh is not None:
            for num, vp_x, vp_y in layout.desktops:
                if vp_x <= mouse_x < vp_x + vw and vp_y <= mouse_y < vp_y + vh:
                    return Placement(num, mouse_x - vp_x, mouse_y - vp_y)

        # 未命中任何范围 -> 回退当前桌面，减去其 VP 偏移
        for num, vp_x, vp_y in layout.desktops:
            if num == layout.current_desktop:
                return Placement(num, mouse_x - vp_x, mouse_y - vp_y)

        return Placement(layout.current_desktop, mouse_x, mouse_y)


class DesktopLayoutProvider:
    """适配友好但脆弱的 `wmctrl -d` 工具链，产出稳定的 DesktopLayout。

    Adapter 模式：把系统命令行的输出格式解析为内部值对象，隔离外部工具
    变迁对核心逻辑的冲击。runner 通过构造注入，便于测试时用 fake 替换。
    """

    def __init__(self, run_command=None):
        self._run = run_command if run_command is not None else self._default_run

    def get_layout(self) -> DesktopLayout | None:
        """执行 wmctrl -d 并解析为布局；失败返回 None。"""
        result = self._run()
        if result is None or getattr(result, "returncode", 0) != 0:
            return None
        return self.parse(result.stdout)

    @staticmethod
    def parse(stdout: str) -> DesktopLayout | None:
        """把 wmctrl -d 的 stdout 文本解析为 DesktopLayout。"""
        desktops = []
        current = None
        viewport_w = viewport_h = None

        for line in stdout.strip().split("\n"):
            if not line.strip():
                continue
            fields = line.split()
            try:
                num = int(fields[0])
            except (ValueError, IndexError):
                continue

            dg = _DG_RE.search(line)
            if dg:
                viewport_w, viewport_h = int(dg.group(1)), int(dg.group(2))

            if "*" in line:
                current = num

            vp = _VP_RE.search(line)
            if vp:
                desktops.append((num, int(vp.group(1)), int(vp.group(2))))
            else:
                desktops.append((num, 0, 0))

        if current is None:
            return None
        return DesktopLayout(current, viewport_w, viewport_h, tuple(desktops))

    @staticmethod
    def _default_run():
        """真实环境下的 wmctrl 调用；异常时返回 None。"""
        try:
            return subprocess.run(
                ["wmctrl", "-d"], capture_output=True, text=True, timeout=3
            )
        except Exception:
            return None


@dataclass(frozen=True)
class PlacementInput:
    """计算窗口几何所需的全部输入。"""

    layout: DesktopLayout | None
    mouse_x: int | None
    mouse_y: int | None
    window_width: int
    window_height: int
    # 布局缺失尺寸时兜底用的屏幕尺寸（通常来自 winfo）
    fallback_screen: tuple = (1920, 1080)
    margin: int = 20
    offset: int = 30


@dataclass(frozen=True)
class WindowPlacement:
    """最终落定的窗口几何结果。"""

    desktop: int | None
    x: int
    y: int
    screen_width: int
    screen_height: int


class WindowPlacementService:
    """把"解析布局 -> 判桌面 -> 算几何"收敛为单一入口。

    Facade 模式：GUI 只调用一个方法，不用关心内部接缝；同时保留组合注入，
    便于测试用 fake 替换被封装的 Provider/Resolver。
    """

    def __init__(self, provider=None, resolver=None):
        self._provider = provider if provider is not None else DesktopLayoutProvider()
        self._resolver = resolver if resolver is not None else DesktopResolver()

    def compute(self, inp: PlacementInput) -> WindowPlacement:
        """纯几何计算：给定布局与鼠标，返回窗口几何。"""
        screen_w, screen_h = inp.fallback_screen
        if inp.layout is not None and inp.layout.viewport_width and inp.layout.viewport_height:
            screen_w, screen_h = inp.layout.viewport_width, inp.layout.viewport_height

        # 从未取词、无鼠标位置 -> 兜底到右下角
        if inp.mouse_x is None or inp.mouse_y is None:
            return WindowPlacement(
                desktop=None,
                x=screen_w - inp.window_width - 50,
                y=screen_h - inp.window_height - 50,
                screen_width=screen_w,
                screen_height=screen_h,
            )

        mouse_x, mouse_y = inp.mouse_x, inp.mouse_y
        # 布局缺失时无法判桌面，按绝对坐标定位
        if inp.layout is None:
            desktop = None
            rel_x, rel_y = mouse_x, mouse_y
        else:
            placement = self._resolver.resolve(inp.layout, mouse_x, mouse_y)
            desktop = placement.desktop
            rel_x, rel_y = placement.rel_x, placement.rel_y

        m, off, w, h = inp.margin, inp.offset, inp.window_width, inp.window_height
        if rel_y - h - off >= m:
            x, y = rel_x - w // 2, rel_y - h - off
        elif rel_y + off + h <= screen_h - m:
            x, y = rel_x - w // 2, rel_y + off
        else:
            x, y = m, m

        x = max(m, min(x, screen_w - w - m))
        y = max(m, min(y, screen_h - h - m))
        return WindowPlacement(desktop, x, y, screen_w, screen_h)

    def current_placement(self, mouse, window_width, window_height, fallback_screen):
        """便捷入口：先取当前布局，再算窗口几何。"""
        layout = self._provider.get_layout()
        mouse_x, mouse_y = (mouse if mouse else (None, None))
        return self.compute(
            PlacementInput(
                layout=layout,
                mouse_x=mouse_x,
                mouse_y=mouse_y,
                window_width=window_width,
                window_height=window_height,
                fallback_screen=fallback_screen,
            )
        )


# ---------------------------------------------------------------------------
# Sticky（驻留所有桌面）
# ---------------------------------------------------------------------------
# 在 Wayland + XWayland 下，Mutter 不响应 xprop 把窗口"移动到指定桌面"。
# 把 _NET_WM_DESKTOP 设为 -1（0xFFFFFFFF）即 Sticky，窗口驻留所有桌面，
# 从而在任何虚拟桌面取词时窗口都可见。以下纯函数统一这类语义。
# ---------------------------------------------------------------------------


def sticky_desktop_value() -> int:
    """Sticky 语义对应的 X 桌面值：-1（0xFFFFFFFF）。"""
    return -1


def is_sticky_desktop(value: int) -> bool:
    """判断读回的桌面值是否为 Sticky（-1 或无符号的 0xFFFFFFFF）。"""
    return value == -1 or value == 0xFFFFFFFF


def net_wm_desktop_literal(sticky: bool = False, desktop: int = 0) -> str:
    """返回写给 xprop 的 _NET_WM_DESKTOP 字面量字符串。

    sticky=True 时写 '-1'；否则写对应桌面的十进制数字。
    """
    if sticky:
        return "-1"
    return str(desktop)


# 全部桌面（Sticky）。EWMH: _NET_WM_DESKTOP = 0xFFFFFFFF 表示驻留所有桌面。
_ALL_DESKTOPS = 0xFFFFFFFF
# source indication：1 表示来自用户/pager，WM 才执行该 ClientMessage。
_SOURCE_USER = 1


def sticky_source_indication() -> int:
    """ClientMessage 的 source indication：用户/pager 申请时为 1。"""
    return _SOURCE_USER


def sticky_client_message_data() -> tuple:
    """构造 _NET_WM_DESKTOP 的 ClientMessage data（5 个 long）。

    返回 (desktop=0xFFFFFFFF, source=1, 0, 0, 0)，即"驻留所有桌面"并标记为
    用户申请。这是 Mutter 真正响应的 Sticky 触发方式（而非写属性）。
    """
    return (_ALL_DESKTOPS, _SOURCE_USER, 0, 0, 0)