
import os
import json
import ctypes
import shutil
import stat
import threading
import tkinter as tk
from tkinter import filedialog, messagebox

# Cấu hình DPI cho màn hình hiển thị sắc nét
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

CONFIG_FILE = "config.json"
USERNAME = os.getlogin()

CACHE_CATEGORIES = {
    "preview": {
        "name": "Cache Xem trước (Preview/Drafts)",
        "paths": [
            rf"C:\Users\{USERNAME}\AppData\Local\CapCut\User Data\Cache",
            rf"C:\Users\{USERNAME}\AppData\Local\CapCut\User Data\Drafts"
        ]
    },
    "proxy": {
        "name": "File Proxy tạm",
        "paths": [
            rf"C:\Users\{USERNAME}\AppData\Local\CapCut\User Data\Proxy"
        ]
    },
    "gpu": {
        "name": "GPU & Shader Cache",
        "paths": [
            rf"C:\Users\{USERNAME}\AppData\Local\CapCut\User Data\GPUCache"
        ]
    },
    "temp": {
        "name": "File rác Temp hệ thống",
        "paths": [
            rf"C:\Users\{USERNAME}\AppData\Local\CapCut\Apps\temp",
            rf"C:\Users\{USERNAME}\AppData\Local\Temp\CapCut"
        ]
    }
}

def load_cfg():
    default_cfg = {
        "x": 200, "y": 200, "w": 340, "h": 90,
        "clean_mode": "all",
        "selected_types": ["preview", "proxy", "gpu", "temp"],
        "sfx_list": []
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                default_cfg.update(data)
        except Exception:
            pass
    return default_cfg

def save_cfg(cfg):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def remove_readonly(func, path, excinfo):
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
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
        self.show_sfx_panel = False
        self.show_settings_panel = False

        self.root.geometry(f'{self.cfg.get("w", 340)}x{self.cfg.get("h", 90)}+{self.cfg.get("x", 200)}+{self.cfg.get("y", 200)}')
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)

        self.transparent_color = "#010101"
        self.root.config(bg=self.transparent_color)
        self.root.wm_attributes("-transparentcolor", self.transparent_color)

        self.main_frame = tk.Frame(root, bg=self.transparent_color)
        self.main_frame.pack(fill="both", expand=True)

        self.canvas = tk.Canvas(self.main_frame, bg=self.transparent_color, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        self.sfx_frame = tk.Frame(self.main_frame, bg="#1e1f29", bd=1, relief="solid")
        self.settings_frame = tk.Frame(self.main_frame, bg="#1e1f29", bd=1, relief="solid")

        self.setup_sfx_ui()
        self.setup_settings_ui()

        self.root.bind("<Configure>", self.on_resize)
        
        # Bắt sự kiện Kéo thả ứng dụng & Resize góc
        self.canvas.bind("<ButtonPress-1>", self.on_canvas_press)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)

    def setup_sfx_ui(self):
        hdr = tk.Frame(self.sfx_frame, bg="#2a2c3a")
        hdr.pack(fill="x", side="top", padx=2, pady=2)
        
        lbl_sfx = tk.Label(hdr, text="🎵 SFX FAVORITES", bg="#2a2c3a", fg="#ffffff", font=("Segoe UI", 8, "bold"))
        lbl_sfx.pack(side="left", padx=5, pady=4)

        btn_add = tk.Button(hdr, text="+ Thêm", bg="#3b3e54", fg="white", bd=0, font=("Segoe UI", 8), command=self.add_sfx_files)
        btn_add.pack(side="right", padx=5)

        self.sfx_listbox = tk.Listbox(self.sfx_frame, bg="#14151d", fg="#e0e0e0", bd=0, 
                                      highlightthickness=0, selectbackground="#3b3e54", 
                                      font=("Segoe UI", 9), activestyle="none")
        self.sfx_listbox.pack(fill="both", expand=True, padx=4, pady=4)

        self.refresh_sfx_listbox()
        self.sfx_listbox.bind("<ButtonPress-1>", self.on_sfx_drag_start)
        self.sfx_listbox.bind("<ButtonRelease-1>", self.on_sfx_drag_end)
        self.sfx_listbox.bind("<Button-3>", self.remove_sfx_item)

    def setup_settings_ui(self):
        hdr = tk.Frame(self.settings_frame, bg="#2a2c3a")
        hdr.pack(fill="x", side="top", padx=2, pady=2)
        
        lbl_st = tk.Label(hdr, text="⚙️ CHẾ ĐỘ XÓA CACHE", bg="#2a2c3a", fg="#ffffff", font=("Segoe UI", 8, "bold"))
        lbl_st.pack(side="left", padx=5, pady=4)

        content = tk.Frame(self.settings_frame, bg="#1e1f29")
        content.pack(fill="both", expand=True, padx=10, pady=5)

        self.mode_var = tk.StringVar(value=self.cfg.get("clean_mode", "all"))
        
        rb_all = tk.Radiobutton(content, text="Xóa TẤT CẢ Thư mục Cache", variable=self.mode_var, value="all",
                                bg="#1e1f29", fg="#ffffff", selectcolor="#2b2d42", activebackground="#1e1f29",
                                activeforeground="#ffffff", font=("Segoe UI", 9, "bold"), command=self.on_mode_change)
        rb_all.pack(anchor="w", pady=(2, 5))

        rb_custom = tk.Radiobutton(content, text="Phân loại theo nhu cầu:", variable=self.mode_var, value="custom",
                                   bg="#1e1f29", fg="#ffffff", selectcolor="#2b2d42", activebackground="#1e1f29",
                                   activeforeground="#ffffff", font=("Segoe UI", 9, "bold"), command=self.on_mode_change)
        rb_custom.pack(anchor="w", pady=(0, 5))

        self.check_vars = {}
        selected_types = self.cfg.get("selected_types", ["preview", "proxy", "gpu", "temp"])

        self.chk_frame = tk.Frame(content, bg="#14151d", bd=1, relief="solid")
        self.chk_frame.pack(fill="both", expand=True, padx=10, pady=2)

        for key, info in CACHE_CATEGORIES.items():
            var = tk.BooleanVar(value=(key in selected_types))
            self.check_vars[key] = var
            chk = tk.Checkbutton(self.chk_frame, text=info["name"], variable=var,
                                 bg="#14151d", fg="#e0e0e0", selectcolor="#2b2d42",
                                 activebackground="#14151d", activeforeground="#ffffff",
                                 font=("Segoe UI", 8), command=self.save_settings)
            chk.pack(anchor="w", padx=8, pady=2)

        self.toggle_chk_state()

    def toggle_chk_state(self):
        is_custom = self.mode_var.get() == "custom"
        for child in self.chk_frame.winfo_children():
            if is_custom:
                child.configure(state="normal")
            else:
                child.configure(state="disabled")

    def on_mode_change(self):
        self.toggle_chk_state()
        self.save_settings()

    def save_settings(self):
        self.cfg["clean_mode"] = self.mode_var.get()
        self.cfg["selected_types"] = [k for k, v in self.check_vars.items() if v.get()]
        save_cfg(self.cfg)

    def refresh_sfx_listbox(self):
        self.sfx_listbox.delete(0, tk.END)
        for path in self.cfg.get("sfx_list", []):
            file_name = os.path.basename(path)
            self.sfx_listbox.insert(tk.END, f" 🔊 {file_name}")

    def add_sfx_files(self):
        files = filedialog.askopenfilenames(
            title="Chọn file âm thanh SFX",
            filetypes=[("Audio Files", "*.mp3 *.wav *.aac *.m4a *.ogg")]
        )
        if files:
            current_list = self.cfg.get("sfx_list", [])
            for f in files:
                norm_p = os.path.normpath(f)
                if norm_p not in current_list:
                    current_list.append(norm_p)
            self.cfg["sfx_list"] = current_list
            save_cfg(self.cfg)
            self.refresh_sfx_listbox()

    def remove_sfx_item(self, event):
        idx = self.sfx_listbox.nearest(event.y)
        if idx >= 0 and idx < len(self.cfg.get("sfx_list", [])):
            file_path = self.cfg["sfx_list"][idx]
            file_name = os.path.basename(file_path)
            dlg = CustomConfirm(self.root, f"Xóa '{file_name[:15]}...'?")
            self.root.wait_window(dlg)
            if dlg.result:
                del self.cfg["sfx_list"][idx]
                save_cfg(self.cfg)
                self.refresh_sfx_listbox()

    def on_sfx_drag_start(self, event):
        idx = self.sfx_listbox.nearest(event.y)
        if idx >= 0 and idx < len(self.cfg.get("sfx_list", [])):
            self.drag_file_path = self.cfg["sfx_list"][idx]

    def on_sfx_drag_end(self, event):
        if hasattr(self, 'drag_file_path') and self.drag_file_path:
            x, y = self.root.winfo_pointerxy()
            rx = self.root.winfo_rootx()
            ry = self.root.winfo_rooty()
            rw = self.root.winfo_width()
            rh = self.root.winfo_height()
            
            if not (rx <= x <= rx + rw and ry <= y <= ry + rh):
                self.copy_file_to_clipboard(self.drag_file_path)
            self.drag_file_path = None

    def copy_file_to_clipboard(self, file_path):
        try:
            command = f'powershell -command "Set-Clipboard -Path \'{file_path}\'"'
            os.system(command)
        except Exception:
            pass

    def draw_ui(self):
        self.canvas.delete("all")
        w = self.root.winfo_width()
        h = self.root.winfo_height()

        if w < 10 or h < 10:
            return

        self.draw_rounded_rect(3, 3, w - 3, h - 3, radius=16, fill="#1e1f29", outline="#3b3e54", width=1.5)
        self.draw_rounded_rect(5, 5, w - 5, max(10, 38), radius=12, fill="#2a2c3a", outline="", width=0)

        # NÚT ĐỎ / XANH - KHÓA VÀ MỞ
        dot_color = "#ff4d4f" if self.locked else "#52c41a"
        dot_glow = "#820014" if self.locked else "#135200"
        
        self.lock_glow = self.canvas.create_oval(12, 12, 26, 26, fill=dot_glow, outline="")
        self.lock_dot = self.canvas.create_oval(14, 14, 24, 24, fill=dot_color, outline="#ffffff", width=1)
        
        self.canvas.tag_bind(self.lock_dot, "<Button-1>", self.toggle_lock)
        self.canvas.tag_bind(self.lock_glow, "<Button-1>", self.toggle_lock)

        # Nút SFX 🎵
        sfx_bg = "#ffb703" if self.show_sfx_panel else "#2b2d42"
        sfx_fg = "#000000" if self.show_sfx_panel else "#ffffff"
        self.btn_sfx_rect = self.draw_rounded_rect(32, 10, 85, 34, radius=6, fill=sfx_bg, outline="#4a4d6b")
        self.btn_sfx_txt = self.canvas.create_text(58, 22, text="🎵 SFX", fill=sfx_fg, font=("Segoe UI", 8, "bold"))
        for el in [self.btn_sfx_rect, self.btn_sfx_txt]:
            self.canvas.tag_bind(el, "<Button-1>", self.toggle_sfx_panel)

        # Nút Cài đặt ⚙️
        st_bg = "#ffb703" if self.show_settings_panel else "#2b2d42"
        st_fg = "#000000" if self.show_settings_panel else "#ffffff"
        self.btn_st_rect = self.draw_rounded_rect(90, 10, 130, 34, radius=6, fill=st_bg, outline="#4a4d6b")
        self.btn_st_txt = self.canvas.create_text(110, 22, text="⚙️", fill=st_fg, font=("Segoe UI", 9, "bold"))
        for el in [self.btn_st_rect, self.btn_st_txt]:
            self.canvas.tag_bind(el, "<Button-1>", self.toggle_settings_panel)

        # Nút Đóng ✕
        self.btn_close_rect = self.draw_rounded_rect(w - 30, 10, w - 10, 34, radius=6, fill="#2b2d42", outline="#4a4d6b")
        self.btn_close_txt = self.canvas.create_text(w - 20, 22, text="✕", fill="#ffffff", font=("Segoe UI", 8, "bold"))
        for el in [self.btn_close_rect, self.btn_close_txt]:
            self.canvas.tag_bind(el, "<Button-1>", self.quit_app)

        btn_text_str = "⏳ WORKING..." if self.is_cleaning else "🧹 CLEAR CACHE"
        btn_fill = "#212333" if (self.locked or self.is_cleaning) else "#2b2d42"
        
        btn_h_bottom = (h - 220) if (self.show_sfx_panel or self.show_settings_panel) else (h - 10)
        self.btn_clear_rect = self.draw_rounded_rect(10, 42, w - 10, max(75, btn_h_bottom), radius=10, fill=btn_fill, outline="#4a4d6b")
        self.btn_clear_txt = self.canvas.create_text(w // 2, 42 + (max(75, btn_h_bottom) - 42) // 2, text=btn_text_str, fill="#ffffff", font=("Segoe UI", 9, "bold"))

        if not self.is_cleaning:
            for el in [self.btn_clear_rect, self.btn_clear_txt]:
                self.canvas.tag_bind(el, "<Button-1>", self.on_clear_click)

        # VÙNG KÉO GIÃN RESIZE Ở GÓC PHẢI DƯỚI (GRIP)
        if not self.locked:
            self.grip = self.canvas.create_polygon(
                w - 18, h - 4, w - 4, h - 18, w - 4, h - 4,
                fill="#ffb703", outline=""
            )

    def on_canvas_press(self, e):
        if self.locked:
            return
            
        w = self.root.winfo_width()
        h = self.root.winfo_height()
        
        # Kiểm tra xem click có trúng khu vực Grip góc dưới bên phải (20x20px) không
        if (w - 22 <= e.x <= w) and (h - 22 <= e.y <= h):
            self.is_resizing = True
            self.start_rw = w
            self.start_rh = h
            self.start_rx = e.x_root
            self.start_ry = e.y_root
        else:
            self.is_resizing = False
            self.mx = e.x_root
            self.my = e.y_root

    def on_canvas_drag(self, e):
        if self.locked:
            return
            
        if getattr(self, 'is_resizing', False):
            # Tính toán kích thước mới khi rê chuột
            new_w = max(260, self.start_rw + (e.x_root - self.start_rx))
            min_h = 320 if (self.show_sfx_panel or self.show_settings_panel) else 90
            new_h = max(min_h, self.start_rh + (e.y_root - self.start_ry))
            self.root.geometry(f"{new_w}x{new_h}")
        else:
            # Di chuyển cửa sổ
            dx = e.x_root - self.mx
            dy = e.y_root - self.my
            self.mx = e.x_root
            self.my = e.y_root
            self.root.geometry(f"+{self.root.winfo_x() + dx}+{self.root.winfo_y() + dy}")

    def toggle_sfx_panel(self, e=None):
        if self.show_settings_panel:
            self.show_settings_panel = False
            self.settings_frame.place_forget()

        self.show_sfx_panel = not self.show_sfx_panel
        if self.show_sfx_panel:
            self.root.geometry(f'{self.root.winfo_width()}x320')
            self.sfx_frame.place(x=10, y=85, width=self.root.winfo_width() - 20, height=220)
        else:
            self.sfx_frame.place_forget()
            self.root.geometry(f'{self.root.winfo_width()}x90')
        self.draw_ui()

    def toggle_settings_panel(self, e=None):
        if self.show_sfx_panel:
            self.show_sfx_panel = False
            self.sfx_frame.place_forget()

        self.show_settings_panel = not self.show_settings_panel
        if self.show_settings_panel:
            self.root.geometry(f'{self.root.winfo_width()}x320')
            self.settings_frame.place(x=10, y=85, width=self.root.winfo_width() - 20, height=220)
        else:
            self.settings_frame.place_forget()
            self.root.geometry(f'{self.root.winfo_width()}x90')
        self.draw_ui()

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

    def on_clear_click(self, e=None):
        mode = self.cfg.get("clean_mode", "all")
        msg = "Xóa TẤT CẢ thư mục Cache CapCut?" if mode == "all" else "Xóa các phân loại Cache đã chọn?"
        
        dlg = CustomConfirm(self.root, msg)
        self.root.wait_window(dlg)
        if dlg.result:
            self.is_cleaning = True
            self.draw_ui()
            threading.Thread(target=self.run_clear_logic, daemon=True).start()

    def run_clear_logic(self):
        mode = self.cfg.get("clean_mode", "all")
        target_paths = []

        if mode == "all":
            for cat in CACHE_CATEGORIES.values():
                target_paths.extend(cat["paths"])
        else:
            selected_types = self.cfg.get("selected_types", [])
            for key in selected_types:
                if key in CACHE_CATEGORIES:
                    target_paths.extend(CACHE_CATEGORIES[key]["paths"])

        success_count = 0
        errors = 0

        for folder_path in target_paths:
            if os.path.exists(folder_path):
                try:
                    shutil.rmtree(folder_path, onerror=remove_readonly)
                    success_count += 1
                except Exception:
                    errors += 1

        def done():
            if success_count > 0:
                msg = f"✨ Đã làm sạch thành công {success_count} thư mục cache!"
                if errors > 0:
                    msg += f"\n(Có {errors} thư mục bị bận do CapCut đang mở)"
            else:
                msg = "✨ Không tìm thấy file rác hoặc các thư mục đã trống sẵn!"
            
            messagebox.showinfo("Kết quả", msg)
            self.is_cleaning = False
            self.draw_ui()

        self.root.after(0, done)

    def on_resize(self, e):
        w = self.root.winfo_width() - 20
        h = self.root.winfo_height() - 95
        if self.show_sfx_panel:
            self.sfx_frame.place(x=10, y=85, width=w, height=h)
        elif self.show_settings_panel:
            self.settings_frame.place(x=10, y=85, width=w, height=h)
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
