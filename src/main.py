"""
Roblox Rivals — AI Aimbot
Python 3.11 · ultralytics 8.2.103 · mss 9.0.1 · pywin32 306
Architecture: tkinter overlay on main thread, aimbot loop on background thread.
No multiprocessing — PyInstaller onefile safe.
"""
from __future__ import annotations

import ctypes
import math
import queue
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import font as tkfont

import cv2
import mss
import numpy as np
import win32api
import win32con
from ultralytics import YOLO

# ── config ────────────────────────────────────────────────────────────────────
MODEL_PATH    = "roblox.pt"      # custom model next to exe; falls back to yolov8n.pt
FALLBACK_PT   = "yolov8n.pt"
TARGET_CLASS  = 0                # 0 = person (COCO); match your custom label id
CONFIDENCE    = 0.40
FOV_PX        = 320
SMOOTHING     = 0.20             # 0 = snap, 1 = no movement
TOGGLE_KEY    = win32con.VK_INSERT
TRIGGER_BTN   = win32con.VK_RBUTTON
HEADSHOT_BIAS = 0.20             # 0 = top of bbox, 0.5 = centre
OVERLAY_MON   = 2                # 1 = primary, 2 = second screen
# ─────────────────────────────────────────────────────────────────────────────

# ── palette ───────────────────────────────────────────────────────────────────
COL_BG       = "#0a0a0a"
COL_PANEL    = "#111111"
COL_BORDER   = "#1e1e1e"
COL_TEXT     = "#e0e0e0"
COL_DIM      = "#555555"
COL_ON       = "#00ff88"
COL_OFF      = "#ff4444"
COL_BAR_BG   = "#1a1a1a"
COL_BAR_LOW  = "#ff4444"
COL_BAR_MID  = "#ffaa00"
COL_BAR_HIGH = "#00ff88"
TRANSPARENT  = "#010101"
PANEL_W      = 320
PANEL_H      = 230
# ─────────────────────────────────────────────────────────────────────────────

_state: dict = {"enabled": False, "conf": 0.0, "detections": 0}
_state_lock  = threading.Lock()


def send_mouse_relative(dx: int, dy: int) -> None:
    dx = int(dx * SMOOTHING)
    dy = int(dy * SMOOTHING)
    if dx == 0 and dy == 0:
        return
    extra = ctypes.c_ulong(0)
    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [("dx", ctypes.c_long), ("dy", ctypes.c_long),
                    ("mouseData", ctypes.c_ulong), ("dwFlags", ctypes.c_ulong),
                    ("time", ctypes.c_ulong),
                    ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]
    class INPUT(ctypes.Structure):
        class _I(ctypes.Union):
            _fields_ = [("mi", MOUSEINPUT)]
        _anonymous_ = ("_i",)
        _fields_ = [("type", ctypes.c_ulong), ("_i", _I)]
    inp = INPUT()
    inp.type = 0
    inp.mi.dx = dx
    inp.mi.dy = dy
    inp.mi.mouseData = 0
    inp.mi.dwFlags = 0x0001
    inp.mi.time = 0
    inp.mi.dwExtraInfo = ctypes.pointer(extra)
    ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))


def capture_roi(sct: mss.base.MSSBase, cx: int, cy: int) -> np.ndarray:
    half = FOV_PX // 2
    region = {"left": cx - half, "top": cy - half,
              "width": FOV_PX, "height": FOV_PX}
    raw = sct.grab(region)
    frame = np.frombuffer(raw.raw, dtype=np.uint8).reshape(raw.height, raw.width, 4)
    return cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)


def best_target(boxes, half: int) -> tuple[tuple[int, int] | None, float]:
    best_dist = float("inf")
    best_pt: tuple[int, int] | None = None
    best_conf = 0.0
    for box in boxes:
        if int(box.cls[0]) != TARGET_CLASS:
            continue
        conf = float(box.conf[0])
        if conf < CONFIDENCE:
            continue
        x1, y1, x2, y2 = box.xyxy[0].tolist()
        bx = (x1 + x2) / 2
        by = y1 + (y2 - y1) * HEADSHOT_BIAS
        dist = math.hypot(bx - half, by - half)
        if dist < best_dist:
            best_dist = dist
            best_pt = (int(bx), int(by))
            best_conf = conf
    return best_pt, best_conf


def aimbot_thread() -> None:
    model_path = MODEL_PATH if Path(MODEL_PATH).exists() else FALLBACK_PT
    model = YOLO(model_path)
    model.fuse()
    u32 = ctypes.windll.user32
    cx = u32.GetSystemMetrics(0) // 2
    cy = u32.GetSystemMetrics(1) // 2
    half = FOV_PX // 2
    enabled = False
    prev_key = False
    print(f"[rivals-aim] model={model_path} | INSERT toggle | RMB aim")
    with mss.mss() as sct:
        while True:
            cur_key = bool(win32api.GetAsyncKeyState(TOGGLE_KEY) & 0x8000)
            if cur_key and not prev_key:
                enabled = not enabled
                print(f"[rivals-aim] {'ON' if enabled else 'OFF'}")
            prev_key = cur_key
            if not enabled:
                with _state_lock:
                    _state["enabled"] = False
                    _state["conf"] = 0.0
                    _state["detections"] = 0
                time.sleep(0.01)
                continue
            trigger = bool(win32api.GetAsyncKeyState(TRIGGER_BTN) & 0x8000)
            frame = capture_roi(sct, cx, cy)
            results = model(frame, verbose=False, stream=False)
            det_count = 0
            top_conf = 0.0
            if results and results[0].boxes is not None:
                det_count = sum(
                    1 for b in results[0].boxes
                    if int(b.cls[0]) == TARGET_CLASS and float(b.conf[0]) >= CONFIDENCE
                )
                pt, top_conf = best_target(results[0].boxes, half)
                if trigger and pt is not None:
                    send_mouse_relative(pt[0] - half, pt[1] - half)
            with _state_lock:
                _state["enabled"] = True
                _state["conf"] = top_conf
                _state["detections"] = det_count


def conf_colour(conf: float) -> str:
    if conf >= 0.75:
        return COL_BAR_HIGH
    if conf >= 0.50:
        return COL_BAR_MID
    return COL_BAR_LOW


def make_clickthrough(hwnd: int) -> None:
    WS_EX_LAYERED = 0x00080000
    WS_EX_TRANSPARENT = 0x00000020
    GWL_EXSTYLE = -20
    LWA_COLORKEY = 0x00000001
    style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    ctypes.windll.user32.SetWindowLongW(
        hwnd, GWL_EXSTYLE, style | WS_EX_LAYERED | WS_EX_TRANSPARENT)
    ctypes.windll.user32.SetLayeredWindowAttributes(
        hwnd, int(TRANSPARENT.lstrip("#"), 16), 0, LWA_COLORKEY)


def run_overlay() -> None:
    try:
        import screeninfo
        monitors = screeninfo.get_monitors()
        idx = min(OVERLAY_MON - 1, len(monitors) - 1)
        mon = monitors[idx]
        mon_x, mon_y, mon_w, mon_h = mon.x, mon.y, mon.width, mon.height
    except Exception:
        sw = ctypes.windll.user32.GetSystemMetrics(0)
        sh = ctypes.windll.user32.GetSystemMetrics(1)
        mon_x, mon_y, mon_w, mon_h = sw, 0, sw, sh
    root = tk.Tk()
    root.title("rivals-aimbot-overlay")
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    root.attributes("-transparentcolor", TRANSPARENT)
    root.configure(bg=TRANSPARENT)
    root.geometry(f"{mon_w}x{mon_h}+{mon_x}+{mon_y}")
    px = mon_w - PANEL_W - 20
    py = mon_h - PANEL_H - 20
    f_title = tkfont.Font(family="Consolas", size=11, weight="bold")
    f_label = tkfont.Font(family="Consolas", size=9)
    f_value = tkfont.Font(family="Consolas", size=22, weight="bold")
    f_small = tkfont.Font(family="Consolas", size=8)
    panel = tk.Frame(root, bg=COL_PANEL,
                     highlightbackground=COL_BORDER, highlightthickness=1)
    panel.place(x=px, y=py, width=PANEL_W, height=PANEL_H)
    tbar = tk.Frame(panel, bg=COL_BORDER, height=28)
    tbar.pack(fill=tk.X)
    tk.Label(tbar, text="  RIVALS AIMBOT", font=f_title,
             bg=COL_BORDER, fg=COL_TEXT).pack(side=tk.LEFT, pady=4)
    status_lbl = tk.Label(tbar, text="● OFF", font=f_label,
                          bg=COL_BORDER, fg=COL_OFF)
    status_lbl.pack(side=tk.RIGHT, padx=10)
    body = tk.Frame(panel, bg=COL_PANEL)
    body.pack(fill=tk.BOTH, expand=True, padx=14, pady=10)
    tk.Label(body, text="CONFIDENCE", font=f_small,
             bg=COL_PANEL, fg=COL_DIM).pack(anchor=tk.W)
    conf_var = tk.StringVar(value="0.0%")
    conf_lbl = tk.Label(body, textvariable=conf_var, font=f_value,
                        bg=COL_PANEL, fg=COL_BAR_LOW)
    conf_lbl.pack(anchor=tk.W)
    bar_frame = tk.Frame(body, bg=COL_BAR_BG, height=8)
    bar_frame.pack(fill=tk.X, pady=(2, 10))
    bar_frame.pack_propagate(False)
    bar_fill = tk.Frame(bar_frame, bg=COL_BAR_LOW, height=8)
    bar_fill.place(x=0, y=0, relheight=1.0, width=0)
    det_frame = tk.Frame(body, bg=COL_PANEL)
    det_frame.pack(fill=tk.X)
    tk.Label(det_frame, text="DETECTIONS", font=f_small,
             bg=COL_PANEL, fg=COL_DIM).pack(side=tk.LEFT)
    det_var = tk.StringVar(value="0")
    tk.Label(det_frame, textvariable=det_var, font=f_label,
             bg=COL_PANEL, fg=COL_TEXT).pack(side=tk.RIGHT)
    tk.Frame(body, bg=COL_BORDER, height=1).pack(fill=tk.X, pady=8)
    tk.Label(body, text="INSERT  toggle  |  RMB  aim", font=f_small,
             bg=COL_PANEL, fg=COL_DIM).pack(anchor=tk.W)
    bar_total = PANEL_W - 28
    def apply_clickthrough() -> None:
        hwnd = ctypes.windll.user32.FindWindowW(None, "rivals-aimbot-overlay")
        if hwnd:
            make_clickthrough(hwnd)
    root.after(300, apply_clickthrough)
    def poll() -> None:
        with _state_lock:
            enabled = _state["enabled"]
            conf = _state["conf"]
            detections = _state["detections"]
        if enabled:
            status_lbl.config(text="● ON", fg=COL_ON)
        else:
            status_lbl.config(text="● OFF", fg=COL_OFF)
            conf = 0.0
            detections = 0
        col = conf_colour(conf)
        conf_var.set(f"{conf * 100:.1f}%")
        conf_lbl.config(fg=col)
        bar_fill.config(bg=col)
        bar_fill.place(x=0, y=0, relheight=1.0, width=int(conf * bar_total))
        det_var.set(str(detections))
        root.after(33, poll)
    root.after(100, poll)
    root.mainloop()


def main() -> None:
    t = threading.Thread(target=aimbot_thread, daemon=True)
    t.start()
    run_overlay()


if __name__ == "__main__":
    main()
