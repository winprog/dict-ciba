"""窗口自动贴合（可增可缩、尊重用户手动调整）纯逻辑回归测试。

锁定两类判定纯函数的行为：
- _should_shrink_window：内容变矮时是否把窗口缩回（仅在用户未手动接管、
  窗口仍停留在自动贴合高度时缩回）
- _resize_is_programmatic：<Configure> 尺寸是否由程序自身生成（初始显示 /
  show_window 重放置 / 自动贴合），避免把程序操作误判为用户手动接管
"""
from dictionary_gui import (
    MIN_WINDOW_LINES,
    WINDOW_SIZE_TOLERANCE,
    _fit_min_window_height,
    _resize_is_programmatic,
    _should_shrink_window,
)


def test_fit_min_window_height_respects_lines_floor():
    """内容行数换算高度高于初始默认高度时，以行数底线为准。"""
    # 10 行 × 20px + 80 非内容区 = 280 < 初值 400 → 取 400
    assert _fit_min_window_height(initial_h=400, lines=10, extra=80, line_h=20) == 400
    # 15 行 × 25px + 100 = 475 > 初值 400 → 以行数底线为准
    assert _fit_min_window_height(initial_h=400, lines=15, extra=100, line_h=25) == 475


def test_fit_min_window_height_never_below_initial():
    """行数换算高度低于初始默认高度时，以初始默认高度为底线（不缩得更小）。"""
    assert _fit_min_window_height(initial_h=400, lines=5, extra=0, line_h=20) == 400


def test_shrink_when_content_shorter_and_window_at_fit_height():
    """窗口停在自动贴合高度、内容变矮 → 应缩回。"""
    assert _should_shrink_window(cur_h=800, target_h=350, auto_fit_h=800) is True


def test_no_shrink_when_never_auto_fitted():
    """auto_fit_height=None（从未被程序撑大）→ 不主动缩小。"""
    assert _should_shrink_window(cur_h=800, target_h=350, auto_fit_h=None) is False


def test_no_shrink_when_user_moved_window():
    """cur_h 与 auto_fit_h 偏差超过 WM 舍入容差（用户手动改过）→ 尊重不缩。"""
    assert _should_shrink_window(cur_h=900, target_h=350, auto_fit_h=800) is False
    # 容差 4 内（如 804）仍视为 WM 舍入 → 允许缩回；超过（如 806）视为用户改动
    assert _should_shrink_window(cur_h=804, target_h=350, auto_fit_h=800) is True
    assert _should_shrink_window(cur_h=806, target_h=350, auto_fit_h=800) is False


def test_no_shrink_when_content_not_shorter():
    """内容未明显变矮（target >= cur）→ 不缩。"""
    assert _should_shrink_window(cur_h=800, target_h=850, auto_fit_h=800) is False


def test_shrink_rule_ignores_floor():
    """缩回底线（initial_window_height）由调用方施加，函数只在允许缩时让 True。

    target=402 仍小于 cur=404 → 允许缩回；target>=cur → 不允许。
    """
    assert _should_shrink_window(cur_h=404, target_h=402, auto_fit_h=404) is True
    assert _should_shrink_window(cur_h=404, target_h=500, auto_fit_h=404) is False


def test_resize_matches_pending_is_programmatic():
    """程序 request 的尺寸（自动贴合/show_window 重放置）→ 程序生成。"""
    assert _resize_is_programmatic(500, 810, cur_w=500, cur_h=807, pending=(500, 810))


def test_resize_matches_pending_with_wm_rounding():
    """WM 舍入容差内（±4px）仍判为程序生成。"""
    assert _resize_is_programmatic(500, 807, cur_w=500, cur_h=807, pending=(500, 810))
    assert _resize_is_programmatic(500, 814, cur_w=500, cur_h=807, pending=(500, 810))


def test_resize_matches_current_is_programmatic():
    """初始显示/<Configure> 与程序记录尺寸一致 → 程序生成。"""
    assert _resize_is_programmatic(500, 400, cur_w=500, cur_h=400, pending=None)


def test_resize_within_tolerance_of_current_is_programmatic():
    """与当前尺寸偏差在容差内（WM 舍入）→ 程序生成。"""
    assert _resize_is_programmatic(501, 402, cur_w=500, cur_h=400, pending=None)


def test_user_drag_is_not_programmatic():
    """用户拖拽改变尺寸，与请求/记录均不一致 → 用户接管。"""
    assert _resize_is_programmatic(500, 900, cur_w=500, cur_h=807, pending=(500, 810)) is False


def test_user_drag_both_axes_is_not_programmatic():
    """拉宽又拉高 → 用户接管。"""
    assert _resize_is_programmatic(640, 900, cur_w=500, cur_h=807, pending=None) is False