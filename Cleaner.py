import os
import json
import ctypes
import threading
import tkinter as tk
from tkinter import filedialog, messagebox

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

CONFIG_FILE = "config.json"
USERNAME = os.getlogin()

DEFAULT_PATHS = [
    rf"C:\Users\{USERNAME}\AppData\Local\CapCut\User Data",
    rf"C:\Users\{USERNAME}\AppData\Local\CapCut\Apps",
]

def load_cfg():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"x": 200, "y": 200, "w": 320, "h": 90, "custom_path": ""}

def save_cfg(cfg):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

class CustomConfirm(tk.Toplevel):
    def __init__(self, parent, msg):
        super().__init__(parent)
        self.result = False
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(bg="#1e1f29")
        
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        px = parent.winfo_x()
        py = parent.winfo_y()
        self.geometry(f"260x110+{px + (pw-260)//2}+{py + (ph-110)//2}")
        
        f_border = tk.Frame(self, bg="#3b3e54", bd=1)
        f_border.pack(fill="both", expand=True)

        lbl = tk.Label(f_border, text=msg, bg="#1e1f29", fg="#ffffff", font=("Segoe UI", 9, "bold"))
        lbl.pack(pady=(18, 12))

        btn_box = tk.Frame(f_border, bg="#1e1f29")
        btn_box.pack()

        btn_no = tk.Button(btn_box, text="Hủy", bg="#2b2d42", fg="white", bd=0, width=8, 
                          command=self.destroy, font=("Segoe UI", 9))
        btn_no.pack(side="left", padx=6)

        btn_yes = tk.Button(btn_box, text="Xóa ngay", bg="#ff4d4f", fg="white", bd=0, width=8, 
                           command=self.on_yes, font=("Segoe UI", 9, "bold"))
        btn_yes.pack(side="left", padx=6)

    def on_yes(self):
        self.result = True
        self.destroy()

class CapCutCleanerApp:
    def __init__(self, root):
        self.root = root
        self.cfg = load_cfg()
        self.locked = False
        self.is_cleaning = False

        self.root.geometry(f'{self.cfg["w"]}x{self.cfg["h"]}+{self.cfg["x"]}+{self.cfg["y"]}')
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)

        self.transparent_color = "#010101"
        self.root.config(bg=self.transparent_color)
        self.root.wm_attributes("-transparentcolor", self.transparent_color)

        self.canvas = tk.Canvas(root, bg=self.transparent_color, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        self.root.bind("<Configure>", self.on_resize)
        self.canvas.bind("<ButtonPress-1>", self.start_move)
        self.canvas.bind("<B1-Motion>", self.do_move)

    def draw_ui(self):
        self.canvas.delete("all")
        w = self.root.winfo_width()
        h = self.root.winfo_height()

        if w < 10 or h < 10:
            return

        self.draw_rounded_rect(3, 3, w - 3, h - 3, radius=16, fill="#1e1f29", outline="#3b3e54", width=1.5)
        self.draw_rounded_rect(5, 5, w - 5, max(10, h // 2), radius=12, fill="#2a2c3a", outline="", width=0)

        dot_color = "#ff4d4f" if self.locked else "#52c41a"
        dot_glow = "#820014" if self.locked else "#135200"
        
        self.lock_glow = self.canvas.create_oval(12, 12, 26, 26, fill=dot_glow, outline="")
        self.lock_dot = self.canvas.create_oval(14, 14, 24, 24, fill=dot_color, outline="#ffffff", width=1)
        
        self.canvas.tag_bind(self.lock_dot, "<Button-1>", self.toggle_lock)
        self.canvas.tag_bind(self.lock_glow, "<Button-1>", self.toggle_lock)

        self.btn_set_rect = self.draw_rounded_rect(32, 10, 60, 38, radius=8, fill="#2b2d42", outline="#4a4d6b")
        self.btn_set_txt = self.canvas.create_text(46, 24, text="⚙️", fill="#ffffff", font=("Segoe UI", 9))
        
        for el in [self.btn_set_rect, self.btn_set_txt]:
            self.canvas.tag_bind(el, "<Button-1>", self.open_settings)

        self.btn_close_rect = self.draw_rounded_rect(w - 32, 10, w - 10, 38, radius=8, fill="#2b2d42", outline="#4a4d6b")
        self.btn_close_txt = self.canvas.create_text(w - 21, 24, text="✕", fill="#ffffff", font=("Segoe UI", 9, "bold"))
        
        for el in [self.btn_close_rect, self.btn_close_txt]:
            self.canvas.tag_bind(el, "<Button-1>", self.quit_app)

        btn_text_str = "⏳ WORKING..." if self.is_cleaning else "🧹 CLEAR CACHE"
        btn_fill = "#212333" if (self.locked or self.is_cleaning) else "#2b2d42"
        
        self.btn_clear_rect = self.draw_rounded_rect(12, 44, w - 24, h - 12, radius=10, fill=btn_fill, outline="#4a4d6b")
        self.btn_clear_txt = self.canvas.create_text(w // 2, 44 + (h - 56) // 2, text=btn_text_str, fill="#ffffff", font=("Segoe UI", 9, "bold"))

        if not self.is_cleaning:
            for el in [self.btn_clear_rect, self.btn_clear_txt]:
                self.canvas.tag_bind(el, "<Button-1>", self.on_clear_click)

        if not self.locked:
            self.grip = self.canvas.create_polygon(
                w - 14, h - 4, w - 4, h - 14, w - 4, h - 4,
                fill="#6c7093", outline=""
            )
            self.canvas.tag_bind(self.grip, "<ButtonPress-1>", self.start_resize)
            self.canvas.tag_bind(self.grip, "<B1-Motion>", self.do_resize)

    def draw_rounded_rect(self, x1, y1, x2, y2, radius=20, **kwargs):
        points = [
            x1 + radius, y1, x1 + radius, y1,
            x2 - radius, y1, x2 - radius, y1,
            x2, y1, x2, y1 + radius, x2, y1 + radius,
            x2, y2 - radius, x2, y2 - radius,
            x2, y2, x2 - radius, y2, x2 - radius, y2,
            x1 + radius, y2, x1 + radius, y2,
            x1, y2, x1, y2 - radius, x1, y2 - radius,
            x1, y1 + radius, x1, y1 + radius, x1, y1
        ]
        return self.canvas.create_polygon(points, smooth=True, **kwargs)

    def toggle_lock(self, e=None):
        self.locked = not self.locked
        self.draw_ui()

    def open_settings(self, e=None):
        path = filedialog.askdirectory(title="Chọn thư mục Cache tùy chỉnh của CapCut")
        if path:
            self.cfg["custom_path"] = os.path.normpath(path)
            save_cfg(self.cfg)
            messagebox.showinfo("Cài đặt", f"Đã lưu đường dẫn:\n{path}")

    def on_clear_click(self, e=None):
        dlg = CustomConfirm(self.root, "Bạn có chắc muốn xóa Cache CapCut?")
        self.root.wait_window(dlg)
        if dlg.result:
            self.is_cleaning = True
            self.draw_ui()
            threading.Thread(target=self.run_clear_logic, daemon=True).start()

    def run_clear_logic(self):
        deleted_files = 0
        freed_bytes = 0
        errors = 0

        target_paths = []
        custom_p = self.cfg.get("custom_path", "")
        if custom_p and os.path.exists(custom_p):
            target_paths.append(custom_p)

        for p in DEFAULT_PATHS:
            if os.path.exists(p) and p not in target_paths:
                target_paths.append(p)

        for base_p in target_paths:
            for root_dir, dirs, files in os.walk(base_p):
                folder_name = os.path.basename(root_dir).lower()
                if any(k in folder_name for k in ["cache", "gpucache", "temp", "preview"]):
                    for file in files:
                        file_path = os.path.join(root_dir, file)
                        try:
                            size = os.path.getsize(file_path)
                            os.remove(file_path)
                            freed_bytes += size
                            deleted_files += 1
                        except Exception:
                            errors += 1

        freed_mb = round(freed_bytes / (1024 * 1024), 2)

        def done():
            msg = f"✨ Đã làm sạch xong!\n\n• Số tệp xóa: {deleted_files}\n• Dung lượng giải phóng: {freed_mb} MB"
            if errors > 0:
                msg += f"\n• Tệp bận (CapCut đang mở): {errors}"
            messagebox.showinfo("Hoàn tất", msg)
            self.is_cleaning = False
            self.draw_ui()

        self.root.after(0, done)

    def start_move(self, e):
        if not self.locked:
            self.mx = e.x_root
            self.my = e.y_root

    def do_move(self, e):
        if not self.locked:
            dx = e.x_root - self.mx
            dy = e.y_root - self.my
            self.mx = e.x_root
            self.my = e.y_root
            self.root.geometry(f"+{self.root.winfo_x() + dx}+{self.root.winfo_y() + dy}")

    def start_resize(self, e):
        if not self.locked:
            self.rw = self.root.winfo_width()
            self.rh = self.root.winfo_height()
            self.rx = e.x_root
            self.ry = e.y_root

    def do_resize(self, e):
        if not self.locked:
            w = max(240, self.rw + (e.x_root - self.rx))
            h = max(80, self.rh + (e.y_root - self.ry))
            self.root.geometry(f"{w}x{h}")

    def on_resize(self, e):
        self.draw_ui()

    def quit_app(self, e=None):
        self.cfg["x"] = self.root.winfo_x()
        self.cfg["y"] = self.root.winfo_y()
        self.cfg["w"] = self.root.winfo_width()
        self.cfg["h"] = self.root.winfo_height()
        save_cfg(self.cfg)
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = CapCutCleanerApp(root)
    root.mainloop()
