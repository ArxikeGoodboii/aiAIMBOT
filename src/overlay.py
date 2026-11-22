from __future__ import annotations
import ctypes, multiprocessing as mp, queue, tkinter as tk
from tkinter import font as tkfont

BG="#010101"; PANEL="#111111"; BORDER="#1e1e1e"; TEXT="#e0e0e0"; DIM="#777777"; ON="#00ff88"; OFF="#ff4444"
PANEL_W,PANEL_H=320,190

def make_clickthrough(hwnd):
    GWL_EXSTYLE=-20; WS_EX_LAYERED=0x00080000; WS_EX_TRANSPARENT=0x20
    style=ctypes.windll.user32.GetWindowLongW(hwnd,GWL_EXSTYLE)
    ctypes.windll.user32.SetWindowLongW(hwnd,GWL_EXSTYLE,style|WS_EX_LAYERED|WS_EX_TRANSPARENT)
    ctypes.windll.user32.SetLayeredWindowAttributes(hwnd,int(BG[1:],16),0,1)

def run_overlay(q: mp.Queue, monitor_index: int):
    from screeninfo import get_monitors
    monitors=get_monitors()
    if not monitors: return
    mon=monitors[min(max(monitor_index-1,0),len(monitors)-1)]
    root=tk.Tk(); root.title("Rivals HUD"); root.overrideredirect(True); root.attributes("-topmost",True)
    root.attributes("-transparentcolor",BG); root.configure(bg=BG)
    x=mon.x+mon.width-PANEL_W-20; y=mon.y+mon.height-PANEL_H-20
    root.geometry(f"{mon.width}x{mon.height}+{mon.x}+{mon.y}")
    panel=tk.Frame(root,bg=PANEL,highlightbackground=BORDER,highlightthickness=1)
    panel.place(x=x,y=y,width=PANEL_W,height=PANEL_H)
    titlefont=tkfont.Font(family="Consolas",size=11,weight="bold")
    label=tkfont.Font(family="Consolas",size=9)
    value=tkfont.Font(family="Consolas",size=22,weight="bold")
    bar=tk.Frame(panel,bg="#222222",height=8); bar.pack(fill=tk.X,padx=14,pady=(10,4)); bar.pack_propagate(False)
    fill=tk.Frame(bar,bg=OFF); fill.place(x=0,y=0,width=0,relheight=1)
    head=tk.Frame(panel,bg=BORDER); head.pack(fill=tk.X)
    tk.Label(head,text="  RIVALS AIMBOT",font=titlefont,bg=BORDER,fg=TEXT).pack(side=tk.LEFT,pady=5)
    status=tk.Label(head,text="● OFF",font=label,bg=BORDER,fg=OFF); status.pack(side=tk.RIGHT,padx=10)
    tk.Label(panel,text="CONFIDENCE",font=label,bg=PANEL,fg=DIM).pack(anchor="w",padx=14,pady=(8,0))
    conf=tk.Label(panel,text="0.0%",font=value,bg=PANEL,fg=OFF); conf.pack(anchor="w",padx=14)
    det=tk.Label(panel,text="DETECTIONS: 0",font=label,bg=PANEL,fg=TEXT); det.pack(anchor="w",padx=14,pady=4)
    tk.Label(panel,text="INSERT toggle  |  Hold RMB to aim",font=label,bg=PANEL,fg=DIM).pack(anchor="w",padx=14,pady=6)
    def clickthrough():
        hwnd=ctypes.windll.user32.FindWindowW(None,"Rivals HUD")
        if hwnd: make_clickthrough(hwnd)
    root.after(250,clickthrough)
    def poll():
        try:
            while True:
                state=q.get_nowait(); enabled=state.get("enabled",False); c=float(state.get("conf",0)); n=int(state.get("detections",0))
                status.config(text="● ON" if enabled else "● OFF",fg=ON if enabled else OFF)
                col=ON if c>=0.75 else "#ffaa00" if c>=0.5 else OFF
                conf.config(text=f"{c*100:.1f}%",fg=col); det.config(text=f"DETECTIONS: {n if enabled else 0}")
                fill.config(bg=col); fill.place(x=0,y=0,width=int(c*(PANEL_W-30)),relheight=1)
        except queue.Empty: pass
        root.after(33,poll)
    root.after(100,poll); root.mainloop()
