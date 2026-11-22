from __future__ import annotations
import sys
import time
import math
import ctypes
import threading
from pathlib import Path

import mss
import numpy as np
import cv2
from ultralytics import YOLO
import win32api
import win32con

MODEL_PATH = "yolov8n.pt"
TARGET_CLASS = 0
CONFIDENCE = 0.45
FOV_PX = 300
SMOOTHING = 0.18
TOGGLE_KEY = win32con.VK_INSERT
TRIGGER_BTN = win32con.VK_RBUTTON
HEADSHOT_BIAS = 0.25


def resource_path(filename: str) -> str:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return str(base / filename)


def screen_center() -> tuple[int, int]:
    user32 = ctypes.windll.user32
    return user32.GetSystemMetrics(0) // 2, user32.GetSystemMetrics(1) // 2


def capture_roi(sct: mss.base.MSSBase, cx: int, cy: int) -> np.ndarray:
    half = FOV_PX // 2
    region = {"left": cx - half, "top": cy - half, "width": FOV_PX, "height": FOV_PX}
    raw = sct.grab(region)
    frame = np.frombuffer(raw.raw, dtype=np.uint8).reshape(raw.height, raw.width, 4)
    return cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)


def nearest_target(boxes) -> tuple[int, int] | None:
    best_dist = float("inf")
    best_pt: tuple[int, int] | None = None
    half = FOV_PX // 2
    for box in boxes:
        if int(box.cls[0]) != TARGET_CLASS or float(box.conf[0]) < CONFIDENCE:
            continue
        x1, y1, x2, y2 = box.xyxy[0].tolist()
        bx = (x1 + x2) / 2
        by = y1 + (y2 - y1) * HEADSHOT_BIAS
        dist = math.hypot(bx - half, by - half)
        if dist < best_dist:
            best_dist = dist
            best_pt = (int(bx), int(by))
    return best_pt


def move_mouse_relative(dx: int, dy: int) -> None:
    if dx == 0 and dy == 0:
        return
    dx = round(dx * SMOOTHING)
    dy = round(dy * SMOOTHING)
    if dx == 0 and dy == 0:
        return
    extra = ctypes.c_ulong(0)

    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [
            ("dx", ctypes.c_long), ("dy", ctypes.c_long),
            ("mouseData", ctypes.c_ulong), ("dwFlags", ctypes.c_ulong),
            ("time", ctypes.c_ulong), ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
        ]

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


def toggle_listener(enabled: list[bool]) -> None:
    previous = False
    while True:
        pressed = bool(win32api.GetAsyncKeyState(TOGGLE_KEY) & 0x8000)
        if pressed and not previous:
            enabled[0] = not enabled[0]
            print(f"[aimbot] {'ON' if enabled[0] else 'OFF'}")
        previous = pressed
        time.sleep(0.05)


def main() -> None:
    model = YOLO(resource_path(MODEL_PATH))
    model.fuse()
    cx, cy = screen_center()
    enabled = [False]
    threading.Thread(target=toggle_listener, args=(enabled,), daemon=True).start()
    print(f"[aimbot] loaded {MODEL_PATH} | INSERT to toggle | RMB to activate")
    with mss.mss() as sct:
        while True:
            if not enabled[0] or not (win32api.GetAsyncKeyState(TRIGGER_BTN) & 0x8000):
                time.sleep(0.01)
                continue
            frame = capture_roi(sct, cx, cy)
            results = model(frame, verbose=False, stream=False)
            if not results or results[0].boxes is None:
                continue
            point = nearest_target(results[0].boxes)
            if point is not None:
                move_mouse_relative(point[0] - FOV_PX // 2, point[1] - FOV_PX // 2)


if __name__ == "__main__":
    main()
