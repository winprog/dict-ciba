"""在 GNOME 50.1 + Wayland 下测试把窗口移到指定桌面的各种方法。

用法: python3 test_desktop_move.py
"""
import subprocess
import time
import sys
import os

def run(cmd, check=False):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
    if check and r.returncode != 0:
        print(f"  [FAIL] rc={r.returncode}")
        if r.stderr:
            print(f"         stderr: {r.stderr.strip()}")
    return r.stdout.strip(), r.returncode

def get_desktop_info():
    out, _ = run("wmctrl -d")
    current = None
    for line in out.split('\n'):
        parts = line.split()
        if len(parts) < 2:
            continue
        if '*' in line:
            current = parts[0]
    return current, out

def find_dict_window():
    out, _ = run("xdotool search --onlyvisible --name 'Dictionary' | head -1")
    if out:
        return out.strip()
    out, _ = run("xdotool search --name 'Dictionary' | head -1")
    return out.strip()

def get_prop(win_id, prop):
    out, _ = run(f"xprop -id {win_id} {prop} 2>/dev/null")
    return out

def wait(w=0.5):
    time.sleep(w)

def test_method(name, setup_fn, action_fn, verify_fn):
    print(f"\n{'='*60}")
    print(f"方法: {name}")
    print(f"{'='*60}")
    try:
        setup_fn()
        wait(0.3)
        action_fn()
        wait(0.5)
        verify_fn()
    except Exception as e:
        print(f"  [异常] {e}")
        import traceback
        traceback.print_exc()


def main():
    print("=" * 60)
    print("GNOME 50.1 窗口桌面移动测试")
    print("=" * 60)

    # ---- 环境准备 ----
    print("\n--- 环境信息 ---")
    out, _ = run("gnome-shell --version 2>/dev/null || echo 'unknown'")
    print(f"  GNOME: {out}")
    out, _ = run(f"echo DISPLAY=$DISPLAY XDG_SESSION_TYPE=$XDG_SESSION_TYPE WAYLAND_DISPLAY=$WAYLAND_DISPLAY")
    print(f"  Session: {out}")

    # ---- 杀掉旧进程，启动 Dictionary ----
    print("\n--- 启动 Dictionary ---")
    run("pkill -f 'python.*dictionary_gui' 2>/dev/null")
    wait(1)
    run("xdotool set_desktop 0")
    wait(0.5)
    cmd = f"cd /home/renxuelei/code/project/dict-ciba && nohup python3 dictionary_gui.py > /tmp/dict_gui.log 2>&1 &"
    run(cmd)
    wait(3)

    win_id = find_dict_window()
    if not win_id:
        print("  [ERROR] 找不到 Dictionary 窗口!")
        return
    print(f"  Dictionary Window ID: {win_id}")

    cur_desktop, wmctrl_out = get_desktop_info()
    print(f"  当前桌面: {cur_desktop}")
    print(f"  wmctrl -d:\n    " + wmctrl_out.replace('\n', '\n    '))

    print(f"\n--- 初始窗口属性 ---")
    print(f"  _NET_WM_DESKTOP: {get_prop(win_id, '_NET_WM_DESKTOP')}")
    print(f"  _NET_WM_STATE: {get_prop(win_id, '_NET_WM_STATE')}")

    # ==========================================
    # 方法 1: 纯 xprop 设置 _NET_WM_DESKTOP
    # ==========================================
    def setup_m1():
        run(f"xdotool set_desktop 0")
        wait(0.3)
        run(f"xdotool get_desktop")

    def action_m1():
        run(f"xprop -id {win_id} -f _NET_WM_DESKTOP 32c -set _NET_WM_DESKTOP 3")

    def verify_m1():
        print(f"  属性: {get_prop(win_id, '_NET_WM_DESKTOP')}")
        for d in range(4):
            run(f"xdotool set_desktop {d}")
            wait(0.5)
            visible, _ = run(f"xdotool search --onlyvisible --name 'Dictionary' | head -1")
            desktop_now, _ = run(f"xdotool get_desktop")
            print(f"  桌面 {desktop_now}: Dictionary 可见={bool(visible)}")

    test_method("方法1: xprop -set _NET_WM_DESKTOP", setup_m1, action_m1, verify_m1)

    # ==========================================
    # 方法 2: xdotool set_desktop_for_window
    # ==========================================
    def setup_m2():
        run(f"xdotool set_desktop 0")
        wait(0.3)

    def action_m2():
        run(f"xdotool set_desktop_for_window {win_id} 1")

    def verify_m2():
        print(f"  属性: {get_prop(win_id, '_NET_WM_DESKTOP')}")
        for d in range(4):
            run(f"xdotool set_desktop {d}")
            wait(0.5)
            visible, _ = run(f"xdotool search --onlyvisible --name 'Dictionary' | head -1")
            desktop_now, _ = run(f"xdotool get_desktop")
            print(f"  桌面 {desktop_now}: Dictionary 可见={bool(visible)}")

    test_method("方法2: xdotool set_desktop_for_window", setup_m2, action_m2, verify_m2)

    # ==========================================
    # 方法 3: python-xlib 直接发 ClientMessage
    # ==========================================
    print(f"\n{'='*60}")
    print(f"方法: python-xlib _NET_WM_DESKTOP ClientMessage")
    print(f"{'='*60}")

    has_xlib = True
    try:
        from Xlib import display as xdisplay
        from Xlib import X
        from Xlib.protocol import event as xevent
    except ImportError:
        has_xlib = False
        print("  python-xlib 未安装, 尝试安装...")
        r = subprocess.run([sys.executable, "-m", "pip", "install", "python-xlib", "-q"], capture_output=True)
        wait(2)
        try:
            from Xlib import display as xdisplay
            from Xlib import X
            from Xlib.protocol import event as xevent
            has_xlib = True
            print("  安装成功!")
        except Exception as e:
            print(f"  安装失败: {e}")

    if has_xlib:
        try:
            run("xdotool set_desktop 0")
            wait(0.3)

            dpy = xdisplay.Display()
            root = dpy.screen().root
            target_win = int(win_id)

            NET_WM_DESKTOP = dpy.intern_atom('_NET_WM_DESKTOP')
            NET_CHANGE_CURRENT_DESKTOP = dpy.intern_atom('_NET_CHANGE_CURRENT_DESKTOP')

            print(f"  目标窗口 (十进制): {target_win}")

            # 构造 ClientMessage 事件
            msg = xevent.ClientMessage(
                window=dpy.create_resource_object('window', target_win),
                client_type=NET_WM_DESKTOP,
                data=(3, [0, 0, 0, 0, 0])  # 移动到桌面 3
            )
            root.send_event(msg, event_mask=X.SubstructureNotifyMask | X.SubstructureRedirectMask)
            dpy.flush()
            wait(0.5)

            print(f"  属性: {get_prop(win_id, '_NET_WM_DESKTOP')}")
            for d in range(4):
                run(f"xdotool set_desktop {d}")
                wait(0.5)
                visible, _ = run(f"xdotool search --onlyvisible --name 'Dictionary' | head -1")
                desktop_now, _ = run(f"xdotool get_desktop")
                print(f"  桌面 {desktop_now}: Dictionary 可见={bool(visible)}")
        except Exception as e:
            print(f"  [异常] {e}")
            import traceback
            traceback.print_exc()

    # ==========================================
    # 方法 4: python-xlib 设置属性 (非 ClientMessage)
    # ==========================================
    if has_xlib:
        print(f"\n{'='*60}")
        print(f"方法: python-xlib XChangeProperty 直接写 _NET_WM_DESKTOP")
        print(f"{'='*60}")

        try:
            run("xdotool set_desktop 0")
            wait(0.3)

            dpy = xdisplay.Display()
            NET_WM_DESKTOP = dpy.intern_atom('_NET_WM_DESKTOP')
            target_win_obj = dpy.create_resource_object('window', int(win_id))

            target_win_obj.change_property(NET_WM_DESKTOP, X.CARDINAL, 32, [3])
            dpy.flush()
            wait(0.5)

            print(f"  属性: {get_prop(win_id, '_NET_WM_DESKTOP')}")
            for d in range(4):
                run(f"xdotool set_desktop {d}")
                wait(0.5)
                visible, _ = run(f"xdotool search --onlyvisible --name 'Dictionary' | head -1")
                desktop_now, _ = run(f"xdotool get_desktop")
                print(f"  桌面 {desktop_now}: Dictionary 可见={bool(visible)}")
        except Exception as e:
            print(f"  [异常] {e}")
            import traceback
            traceback.print_exc()

    # ==========================================
    # 方法 5: 添加 _NET_WM_STATE_STICKY
    # ==========================================
    print(f"\n{'='*60}")
    print(f"方法: 测试 STICKY 状态")
    print(f"{'='*60}")

    run(f"xdotool set_desktop 0")
    wait(0.3)
    run(f"xprop -id {win_id} -f _NET_WM_STATE 32a -add _NET_WM_STATE_STICKY 2>/dev/null")
    wait(0.3)
    print(f"  加 STICKY 后 STATE: {get_prop(win_id, '_NET_WM_STATE')}")
    run(f"xdotool set_desktop 2")
    wait(0.5)
    print(f"  切到桌面 2 后可见: {bool(run(f'xdotool search --onlyvisible --name Dictionary')[0])}")

    run(f"xprop -id {win_id} -f _NET_WM_STATE 32a -remove _NET_WM_STATE_STICKY 2>/dev/null")
    wait(0.3)
    print(f"  去掉 STICKY 后 STATE: {get_prop(win_id, '_NET_WM_STATE')}")

    # ==========================================
    # 方法 6: Mutter / GNOME Shell DBus
    # ==========================================
    print(f"\n{'='*60}")
    print(f"方法: GNOME Shell Mutter DBus")
    print(f"{'='*60}")

    try:
        import pydbus
        print("  pydbus 可用, 列出 shell / mutter 接口...")
        bus = pydbus.SessionBus()
        try:
            shell = bus.get('org.gnome.Shell', '/org/gnome/Shell')
            print(f"  org.gnome.Shell methods: {[m for m in dir(shell) if not m.startswith('_')]}")
        except Exception as e:
            print(f"  org.gnome.Shell: {e}")
    except ImportError:
        print("  pydbus 未安装")
    except Exception as e:
        print(f"  dbus error: {e}")

    out, _ = run("gdbus introspect --session --dest org.gnome.Shell --object-path /org/gnome/Shell 2>&1")
    print(f"  Shell introspect: {out[:500]}")

    # ==========================================
    # 最终状态
    # ==========================================
    print(f"\n{'='*60}")
    print(f"所有方法测试完毕, Dictionary 保留运行中")
    print(f"{'='*60}")
    print(f"  Dictionary 日志在: /tmp/dict_gui.log")
    print(f"  窗口 ID: {win_id}")

if __name__ == "__main__":
    main()