from __future__ import annotations
import ctypes, math, multiprocessing as mp, sys, threading, time
from pathlib import Path
import cv2, mss, numpy as np, win32api, win32con
from ultralytics import YOLO

MODEL_PATH = "roblox.pt"
FALLBACK_PT = "yolov8n.pt"
TARGET_CLASS = 0
CONFIDENCE = 0.40
FOV_PX = 320
SMOOTHING = 0.20
TOGGLE_KEY = win32con.VK_INSERT
TRIGGER_BTN = win32con.VK_RBUTTON
HEADSHOT_BIAS = 0.20
OVERLAY_MON = 2

def resource_path(name: str) -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)) / name

def screen_center():
    u = ctypes.windll.user32
    return u.GetSystemMetrics(0)//2, u.GetSystemMetrics(1)//2

def capture_roi(sct, cx, cy):
    half = FOV_PX//2
    raw = sct.grab({"left":cx-half,"top":cy-half,"width":FOV_PX,"height":FOV_PX})
    frame = np.frombuffer(raw.raw,dtype=np.uint8).reshape(raw.height,raw.width,4)
    return cv2.cvtColor(frame,cv2.COLOR_BGRA2BGR)

def best_target(boxes, half):
    best_dist, best_pt, best_conf = float("inf"), None, 0.0
    for box in boxes:
        if int(box.cls[0]) != TARGET_CLASS: continue
        conf = float(box.conf[0])
        if conf < CONFIDENCE: continue
        x1,y1,x2,y2 = box.xyxy[0].tolist()
        bx,by = (x1+x2)/2, y1+(y2-y1)*HEADSHOT_BIAS
        dist = math.hypot(bx-half,by-half)
        if dist < best_dist:
            best_dist,best_pt,best_conf = dist,(int(bx),int(by)),conf
    return best_pt,best_conf

def send_mouse_relative(dx,dy):
    dx,dy = int(dx*SMOOTHING),int(dy*SMOOTHING)
    if not dx and not dy: return
    extra=ctypes.c_ulong(0)
    class MOUSEINPUT(ctypes.Structure):
        _fields_=[("dx",ctypes.c_long),("dy",ctypes.c_long),("mouseData",ctypes.c_ulong),("dwFlags",ctypes.c_ulong),("time",ctypes.c_ulong),("dwExtraInfo",ctypes.POINTER(ctypes.c_ulong))]
    class INPUT(ctypes.Structure):
        class _I(ctypes.Union): _fields_=[("mi",MOUSEINPUT)]
        _anonymous_=("_i",)
        _fields_=[("type",ctypes.c_ulong),("_i",_I)]
    inp=INPUT(); inp.type=0; inp.mi.dx=dx; inp.mi.dy=dy; inp.mi.mouseData=0; inp.mi.dwFlags=1; inp.mi.time=0; inp.mi.dwExtraInfo=ctypes.pointer(extra)
    ctypes.windll.user32.SendInput(1,ctypes.byref(inp),ctypes.sizeof(inp))

def toggle_thread(enabled):
    prev=False
    while True:
        cur=bool(win32api.GetAsyncKeyState(TOGGLE_KEY)&0x8000)
        if cur and not prev:
            enabled[0]=not enabled[0]; print("[rivals-aim]", "ON" if enabled[0] else "OFF")
        prev=cur; time.sleep(0.05)

def aimbot_loop(q):
    custom=Path(MODEL_PATH)
    model_path=custom if custom.exists() else resource_path(FALLBACK_PT)
    model=YOLO(str(model_path)); model.fuse()
    print(f"[rivals-aim] model={model_path} | INSERT toggle | RMB aim")
    cx,cy=screen_center(); half=FOV_PX//2; enabled=[False]
    threading.Thread(target=toggle_thread,args=(enabled,),daemon=True).start()
    q.put({"enabled":False,"conf":0.0,"detections":0,"fov":FOV_PX})
    with mss.mss() as sct:
        while True:
            if not enabled[0]:
                try: q.put_nowait({"enabled":False,"conf":0.0,"detections":0,"fov":FOV_PX})
                except Exception: pass
                time.sleep(0.01); continue
            trigger=bool(win32api.GetAsyncKeyState(TRIGGER_BTN)&0x8000)
            results=model(capture_roi(sct,cx,cy),verbose=False,stream=False)
            det_count,top_conf=0,0.0
            if results and results[0].boxes is not None:
                det_count=sum(1 for b in results[0].boxes if int(b.cls[0])==TARGET_CLASS and float(b.conf[0])>=CONFIDENCE)
                pt,top_conf=best_target(results[0].boxes,half)
                if trigger and pt is not None: send_mouse_relative(pt[0]-half,pt[1]-half)
            try: q.put_nowait({"enabled":True,"conf":top_conf,"detections":det_count,"fov":FOV_PX})
            except Exception: pass

def main():
    mp.freeze_support()
    q=mp.Queue(maxsize=4)
    from overlay import run_overlay
    mp.Process(target=run_overlay,args=(q,OVERLAY_MON),daemon=True).start()
    aimbot_loop(q)

if __name__=="__main__": main()
