"""GJS Eval 调用方式调试 + 解决 Dictionary 多桌面问题。"""
import subprocess, time, sys

def run(cmd, timeout=10):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
    return r.stdout.strip(), r.stderr.strip(), r.returncode

# ============ 先启动 Dictionary ============
print("=== 启动 Dictionary ===")
run("pkill -f 'dictionary_gui' 2>/dev/null")
time.sleep(1)
run("xdotool set_desktop 0")
time.sleep(0.5)
run("cd /home/renxuelei/code/project/dict-ciba && nohup python3 dictionary_gui.py > /tmp/dict_gui.log 2>&1 &")
time.sleep(3)

WIN_ID = run("xdotool search --name Dictionary | head -1")[0]
print(f"Dictionary WinID: {WIN_ID}")

if not WIN_ID:
    print(open('/tmp/dict_gui.log').read()[-500:])
    sys.exit(1)

# ============ GJS Eval 最小测试 ============
print("\n=== GJS Eval 调试 ===")

tests = [
    ("最简单的 true", "true"),
    ("最简单的字符串", '"hello"'),
    ("global 检查", "typeof global"),
    ("workspace_manager 检查", "typeof global.workspace_manager"),
    ("window_actors 数量", "global.get_window_actors().length"),
    ("global.get_window_actors()", "JSON.stringify(global.get_window_actors().length)"),
]

for label, script in tests:
    # 关键: GNOME Shell Eval 的参数是 (string script)
    # 返回 (boolean success, string output)
    # 所以 gdbus call 应该只传一个字符串参数
    cmd = f'gdbus call --session --dest org.gnome.Shell --object-path /org/gnome/Shell --method org.gnome.Shell.Eval "{script}"'
    out, err, rc = run(cmd)
    print(f"  {label}:")
    print(f"    cmd: {cmd[:100]}")
    print(f"    out={out}")
    if err: print(f"    err={err}")

# ============ 用 gdbus --method-call 格式也试试 ============
print("\n=== 用 gdbus --method-call 格式 ===")
for script in ["true", '"hello"', "global.get_window_actors().length"]:
    cmd = f"gdbus call --session --dest org.gnome.Shell --object-path /org/gnome/Shell --method org.gnome.Shell.Eval '{script}'"
    out, err, rc = run(cmd)
    print(f"  script={script!r}: out={out}, err={err}")

# ============ 再试试 Python subprocess 列表参数 (避免 shell 转义) ============
print("\n=== 用 Python 列表参数调 gdbus (正确的 dbus 方式) ===")
import shlex

def gjs_eval_python(script):
    proc = subprocess.run(
        ["gdbus", "call", "--session",
         "--dest", "org.gnome.Shell",
         "--object-path", "/org/gnome/Shell",
         "--method", "org.gnome.Shell.Eval",
         script],
        capture_output=True, text=True, timeout=10
    )
    return proc.stdout.strip(), proc.stderr.strip(), proc.returncode

for label, script in [
    ("true", "true"),
    ("hello", '"hello"'),
    ("typeof global", "typeof global"),
    ("ws count", "global.workspace_manager.get_n_workspaces()"),
    ("windows count", "global.get_window_actors().length"),
]:
    out, err, rc = gjs_eval_python(script)
    print(f"  {label}: out={out}, err={err}")

# ============ 找 Dictionary 窗口 (用正确方式) ============
print("\n=== 找 Dictionary 窗口对象 ===")
# 在 GNOME Shell 里，我们需要找到 X11 window actor 对应的对象
# 方法: 遍历 window_actors, 看哪个的 X11 window id 匹配我们的 WIN_ID

find_script = f'''
(function() {{
    let wins = global.get_window_actors();
    let targetId = 0x{int(WIN_ID):x};
    for (let i = 0; i < wins.length; i++) {{
        let w = wins[i].get_window();
        let xid = w.get_x11_window ? w.get_x11_window() : null;
        let title = w.get_title();
        if (title === "Dictionary" || xid === targetId) {{
            return JSON.stringify({{
                idx: i,
                title: title,
                xid: xid,
                ws: wins[i].get_workspace_index(),
                ws_count: global.workspace_manager.get_n_workspaces(),
                hasMove: typeof wins[i].move_to_workspace
            }});
        }}
    }}
    return "NOT FOUND, xid=" + targetId + ", total=" + wins.length;
}})();
'''

out, err, rc = gjs_eval_python(find_script.strip())
print(f"Find result: out={out}, err={err}")

# ============ 如果找到了, 尝试移动 ============
if "NOT FOUND" not in out and out:
    print("\n=== 尝试 GJS move_to_workspace ===")
    run("xdotool set_desktop 0"); time.sleep(0.5)
    
    move_script = f'''
    (function() {{
        let wins = global.get_window_actors();
        for (let i = 0; i < wins.length; i++) {{
            let w = wins[i];
            if (w.get_window().get_title() === "Dictionary") {{
                w.move_to_workspace(2);
                return "moved, ws=" + w.get_workspace_index();
            }}
        }}
        return "NOT FOUND";
    }})();
    '''
    out, err, rc = gjs_eval_python(move_script.strip())
    print(f"move result: out={out}, err={err}")
    time.sleep(1)

    print("\n=== 验证 ===")
    for d in range(4):
        run(f"xdotool set_desktop {d}"); time.sleep(0.3)
        vis = run(f"xdotool search --onlyvisible --name Dictionary | head -1")[0]
        print(f"  desktop {d}: visible={bool(vis.strip())}")

# ============ 也查一下 Mutter 50 是否完全不认 _NET_WM_DESKTOP ============
print("\n=== xprop -set 再试一次 + 验证 Mutter 是否忽略 ===")
run("xdotool set_desktop 0"); time.sleep(0.3)
run(f"xprop -id {WIN_ID} -f _NET_WM_DESKTOP 32c -set _NET_WM_DESKTOP 3 2>&1")
time.sleep(0.5)
out = run(f"xprop -id {WIN_ID} _NET_WM_DESKTOP 2>&1")[0]
print(f"  xprop 写入后: {out}")
for d in range(4):
    run(f"xdotool set_desktop {d}"); time.sleep(0.3)
    vis = run(f"xdotool search --onlyvisible --name Dictionary | head -1")[0]
    print(f"  desktop {d}: visible={bool(vis.strip())}")