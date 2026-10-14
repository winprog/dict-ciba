"""窗口放置与置顶管理（P2 拆分）。

承接 DictionaryApp 原 show_window / _find_x11_window_id / _ensure_window_sticky，
将窗口几何计算、X11 查找、Sticky(跨虚拟桌面驻留) 从 UI 类中解耦。
"""

import subprocess

try:
    from services.logger import get_logger
except Exception:  # 独立运行兜底
    import logging
    get_logger = logging.getLogger


class WindowManager:
    """管理翻译窗口的几何放置与 Wayland 下的跨桌面 sticky。

    持有 tkinter root 引用；不持有任何视图控件，UI 状态（按钮文字、
    可见性标志）由调用方 DictionaryApp 自行维护。
    """

    def __init__(self, root, placement_service):
        self._root = root
        self._placement = placement_service
        self._log = get_logger(__name__)

    def place_window(self, mouse, window_width, window_height):
        """根据鼠标位置避开取词点放置窗口，并安排 sticky。

        mouse: (x, y) 取词时鼠标坐标；window_width/height: 当前窗口尺寸。
        返回 (x, y) 实际落点（便于调用方取用）。
        """
        screen = (self._root.winfo_screenwidth(), self._root.winfo_screenheight())
        self._log.debug(
            f"📐 [place] screen={screen[0]}x{screen[1]}, window={window_width}x{window_height}, mouse={mouse}"
        )

        placement = self._placement.avoid_current_placement(
            mouse, window_width, window_height, screen
        )
        x, y, target_desktop = placement.x, placement.y, placement.desktop
        self._log.debug(f"📐 [place] geometry={window_width}x{window_height}+{x}+{y}, desktop={target_desktop}")

        self._root.deiconify()
        self._root.geometry(f"{window_width}x{window_height}+{x}+{y}")
        self._root.update_idletasks()

        if target_desktop is not None:
            self._root.after(100, self.ensure_sticky)
        return x, y

    def _find_x11_window_id(self):
        """用 xdotool 找到窗口的 X11 Window ID（十进制）。

        GNOME 50.1 + Wayland 下 wmctrl -l 会段错误，故用 xdotool search。
        """
        for args in (
            ['xdotool', 'search', '--onlyvisible', '--name', 'Dictionary'],
            ['xdotool', 'search', '--name', 'Dictionary'],
        ):
            try:
                r = subprocess.run(args, capture_output=True, text=True, timeout=3)
                if r.returncode == 0 and r.stdout.strip():
                    return r.stdout.strip().split('\n')[0]
            except Exception:
                pass
        return None

    def ensure_sticky(self):
        """让窗口驻留所有虚拟桌面（Sticky）。

        关键：GNOME 50.1 + Wayland 下，Mutter 不响应 xprop 改写
        _NET_WM_DESKTOP 属性，只响应其 ClientMessage 通知（source=1），
        故通过 python-xlib 向 root 发送该事件让窗口跨桌面可见。
        """
        try:
            win_id = self._find_x11_window_id()
            self._log.debug(f"🖥️ [sticky] X11 Window ID: {win_id}")
            if win_id is None:
                self._log.debug(f"🖥️ [sticky] 窗口未就绪, 200ms 后重试")
                self._root.after(200, self.ensure_sticky)
                return

            from Xlib import display as xdisplay, X
            from Xlib.protocol import event as xevent
            from services.desktop_placement import sticky_client_message_data

            d = xdisplay.Display()
            root = d.screen().root
            w = d.create_resource_object('window', int(win_id))
            atom = d.intern_atom('_NET_WM_DESKTOP')
            msg = xevent.ClientMessage(
                window=w,
                client_type=atom,
                data=(32, sticky_client_message_data()),
            )
            root.send_event(
                msg,
                event_mask=X.SubstructureRedirectMask | X.SubstructureNotifyMask,
            )
            d.flush()
            self._log.debug(f"🖥️ [sticky] 已发送 sticky ClientMessage")

            subprocess.run(['xdotool', 'windowactivate', win_id],
                           capture_output=True, text=True, timeout=3)

            self._root.deiconify()
            self._root.lift()
            self._root.focus_force()
            self._log.debug(f"🖥️ [sticky] 完成")
        except Exception as e:
            self._log.warning(f"🖥️ [sticky] 异常: {e}")