import os
import json
import ctypes
import shutil
import stat
import threading
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

# Cấu hình DPI sắc nét trên Windows
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

# Khởi tạo Pygame Mixer để nghe thử âm thanh SFX
try:
    import pygame
    pygame.mixer.init()
    HAS_PYGAME = True
except Exception:
    HAS_PYGAME = False

CONFIG_FILE = "config.json"
USERNAME = os.getlogin()

# Bổ trợ Kéo Thả Chuẩn Native Windows (CF_HDROP)
def set_clipboard_files(files):
    from ctypes import windll, c_char
    import struct

    GMEM_ZEROINIT = 0x0040
    GMEM_MOVEABLE = 0x0002
    CF_HDROP = 15

    offset = 20
    data = bytearray(struct.pack('IiiII', offset, 0, 0, 0, 1))
    for file in files:
        data.extend(file.encode('utf-16le'))
        data.extend(b'\x00\x00')
    data.extend(b'\x00\x00')

    windll.user32.OpenClipboard(0)
    windll.user32.EmptyClipboard()
    
    h_global = windll.kernel32.GlobalAlloc(GMEM_MOVEABLE | GMEM_ZEROINIT, len(data))
    p_global = windll.kernel32.GlobalLock(h_global)
    
    cdll_msvcrt = ctypes.CDLL('msvcrt')
    cdll_msvcrt.memcpy(p_global, (c_char * len(data)).from_buffer(data), len(data))
    
    windll.kernel32.GlobalUnlock(h_global)
    windll.user32.SetClipboardData(CF_HDROP, h_global)
    windll.user32.CloseClipboard()

CACHE_CATEGORIES = {
    "preview": {"name": "Cache Xem trước (Preview/Drafts)", "paths": [rf"C:\Users\{USERNAME}\AppData\Local\CapCut\User Data\Cache", rf"C:\Users\{USERNAME}\AppData\Local\CapCut\User Data\Drafts"]},
    "proxy": {"name": "File Proxy tạm", "paths": [rf"C:\Users\{USERNAME}\AppData\Local\CapCut\User Data\Proxy"]},
    "gpu": {"name": "GPU & Shader Cache", "paths": [rf"C:\Users\{USERNAME}\AppData\Local\CapCut\User Data\GPUCache"]},
    "temp": {"name": "File rác Temp hệ thống", "paths": [rf"C:\Users\{USERNAME}\AppData\Local\CapCut\Apps\temp", rf"C:\Users\{USERNAME}\AppData\Local\Temp\CapCut"]}
}

def load_cfg():
    default_cfg = {
        "x": 200, "y": 200, "w": 420, "h": 90,
        "clean_mode": "all",
        "selected_types": ["preview", "proxy", "gpu", "temp"],
        "custom_folders": [],
        "sfx_data": {"Tất cả": []},
        "clip_data": {"Tất cả": []},
        "prompt_data": {"Chung": []},
        "hotkey": "<Control-Alt-c>"
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
        
        pw, ph = parent.winfo_width(), parent.winfo_height()
        px, py = parent.winfo_x(), parent.winfo_y()
        self.geometry(f"280x120+{px + (pw-280)//2}+{py + (ph-120)//2}")
        
        f_border = tk.Frame(self, bg="#3b3e54", bd=1)
        f_border.pack(fill="both", expand=True)

        lbl = tk.Label(f_border, text=msg, bg="#1e1f29", fg="#ffffff", font=("Segoe UI", 9, "bold"), wraplength=260)
        lbl.pack(pady=(18, 12))

        btn_box = tk.Frame(f_border, bg="#1e1f29")
        btn_box.pack()

        btn_no = tk.Button(btn_box, text="Hủy", bg="#2b2d42", fg="white", bd=0, width=8, command=self.destroy, font=("Segoe UI", 9))
        btn_no.pack(side="left", padx=6)

        btn_yes = tk.Button(btn_box, text="Đồng ý", bg="#ff4d4f", fg="white", bd=0, width=8, command=self.on_yes, font=("Segoe UI", 9, "bold"))
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
        self.active_panel = None
        self.is_hidden = False
        self.animating = False

        self.root.geometry(f'{self.cfg.get("w", 420)}x{self.cfg.get("h", 90)}+{self.cfg.get("x", 200)}+{self.cfg.get("y", 200)}')
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)

        self.transparent_color = "#010101"
        self.root.config(bg=self.transparent_color)
        self.root.wm_attributes("-transparentcolor", self.transparent_color)

        self.main_frame = tk.Frame(root, bg=self.transparent_color)
        self.main_frame.pack(fill="both", expand=True)

        self.canvas = tk.Canvas(self.main_frame, bg=self.transparent_color, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        self.clips_frame = tk.Frame(self.main_frame, bg="#1e1f29", bd=1, relief="solid")
        self.sfx_frame = tk.Frame(self.main_frame, bg="#1e1f29", bd=1, relief="solid")
        self.prompts_frame = tk.Frame(self.main_frame, bg="#1e1f29", bd=1, relief="solid")
        self.settings_frame = tk.Frame(self.main_frame, bg="#1e1f29", bd=1, relief="solid")

        self.setup_clips_ui()
        self.setup_sfx_ui()
        self.setup_prompts_ui()
        self.setup_settings_ui()

        self.root.bind("<Configure>", self.on_resize)
        self.canvas.bind("<ButtonPress-1>", self.on_canvas_press)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)

        try:
            self.root.bind_all(self.cfg.get("hotkey", "<Control-Alt-c>"), self.toggle_visibility_animated)
        except Exception:
            pass

    def setup_clips_ui(self):
        hdr = tk.Frame(self.clips_frame, bg="#2a2c3a")
        hdr.pack(fill="x", side="top", padx=2, pady=2)
        
        lbl = tk.Label(hdr, text="🎬 CLIPS & PRESETS", bg="#2a2c3a", fg="#ffffff", font=("Segoe UI", 8, "bold"))
        lbl.pack(side="left", padx=5, pady=4)

        btn_add_cat = tk.Button(hdr, text="+ Nhóm", bg="#3b3e54", fg="white", bd=0, font=("Segoe UI", 8), command=lambda: self.add_category("clip"))
        btn_add_cat.pack(side="right", padx=2)

        btn_add = tk.Button(hdr, text="+ File", bg="#ffb703", fg="black", bd=0, font=("Segoe UI", 8, "bold"), command=self.add_clip_files)
        btn_add.pack(side="right", padx=2)

        self.clip_cat_var = tk.StringVar(value="Tất cả")
        self.clip_cat_cb = ttk.Combobox(hdr, textvariable=self.clip_cat_var, state="readonly", width=10)
        self.clip_cat_cb.pack(side="right", padx=5)
        self.clip_cat_cb.bind("<<ComboboxSelected>>", lambda e: self.refresh_clip_listbox())

        self.clip_listbox = tk.Listbox(self.clips_frame, bg="#14151d", fg="#e0e0e0", bd=0, 
                                       highlightthickness=0, selectbackground="#ffb703", selectforeground="#000000",
                                       font=("Segoe UI", 9), activestyle="none")
        self.clip_listbox.pack(fill="both", expand=True, padx=4, pady=4)

        self.refresh_clip_categories()
        self.clip_listbox.bind("<ButtonPress-1>", lambda e: self.on_drag_start(e, "clip"))
        self.clip_listbox.bind("<B1-Motion>", self.on_dragging)
        self.clip_listbox.bind("<ButtonRelease-1>", self.on_drag_end)
        self.clip_listbox.bind("<Button-3>", lambda e: self.remove_item(e, "clip"))

    def setup_sfx_ui(self):
        hdr = tk.Frame(self.sfx_frame, bg="#2a2c3a")
        hdr.pack(fill="x", side="top", padx=2, pady=2)
        
        lbl_sfx = tk.Label(hdr, text="🎵 SFX HIỆU ỨNG", bg="#2a2c3a", fg="#ffffff", font=("Segoe UI", 8, "bold"))
        lbl_sfx.pack(side="left", padx=5, pady=4)

        btn_add_cat = tk.Button(hdr, text="+ Nhóm", bg="#3b3e54", fg="white", bd=0, font=("Segoe UI", 8), command=lambda: self.add_category("sfx"))
        btn_add_cat.pack(side="right", padx=2)

        btn_add = tk.Button(hdr, text="+ File", bg="#ffb703", fg="black", bd=0, font=("Segoe UI", 8, "bold"), command=self.add_sfx_files)
        btn_add.pack(side="right", padx=2)

        self.sfx_cat_var = tk.StringVar(value="Tất cả")
        self.sfx_cat_cb = ttk.Combobox(hdr, textvariable=self.sfx_cat_var, state="readonly", width=10)
        self.sfx_cat_cb.pack(side="right", padx=5)
        self.sfx_cat_cb.bind("<<ComboboxSelected>>", lambda e: self.refresh_sfx_listbox())

        self.sfx_listbox = tk.Listbox(self.sfx_frame, bg="#14151d", fg="#e0e0e0", bd=0, 
                                      highlightthickness=0, selectbackground="#ffb703", selectforeground="#000000",
                                      font=("Segoe UI", 9), activestyle="none")
        self.sfx_listbox.pack(fill="both", expand=True, padx=4, pady=4)

        self.refresh_sfx_categories()
        
        self.sfx_listbox.bind("<ButtonPress-1>", lambda e: self.on_sfx_click_and_drag(e))
        self.sfx_listbox.bind("<B1-Motion>", self.on_dragging)
        self.sfx_listbox.bind("<ButtonRelease-1>", self.on_drag_end)
        self.sfx_listbox.bind("<Button-3>", lambda e: self.remove_item(e, "sfx"))

    def setup_prompts_ui(self):
        hdr = tk.Frame(self.prompts_frame, bg="#2a2c3a")
        hdr.pack(fill="x", side="top", padx=2, pady=2)
        
        lbl = tk.Label(hdr, text="💡 BỘ PROMPTS", bg="#2a2c3a", fg="#ffffff", font=("Segoe UI", 8, "bold"))
        lbl.pack(side="left", padx=5, pady=4)

        btn_add_cat = tk.Button(hdr, text="+ Nhóm", bg="#3b3e54", fg="white", bd=0, font=("Segoe UI", 8), command=lambda: self.add_category("prompt"))
        btn_add_cat.pack(side="right", padx=2)

        btn_add = tk.Button(hdr, text="+ Prompt", bg="#ffb703", fg="black", bd=0, font=("Segoe UI", 8, "bold"), command=self.add_prompt_item)
        btn_add.pack(side="right", padx=2)

        self.prompt_cat_var = tk.StringVar(value="Chung")
        self.prompt_cat_cb = ttk.Combobox(hdr, textvariable=self.prompt_cat_var, state="readonly", width=10)
        self.prompt_cat_cb.pack(side="right", padx=5)
        self.prompt_cat_cb.bind("<<ComboboxSelected>>", lambda e: self.refresh_prompt_listbox())

        self.prompt_listbox = tk.Listbox(self.prompts_frame, bg="#14151d", fg="#e0e0e0", bd=0, 
                                         highlightthickness=0, selectbackground="#52c41a", selectforeground="#ffffff",
                                         font=("Segoe UI", 9), activestyle="none")
        self.prompt_listbox.pack(fill="both", expand=True, padx=4, pady=4)

        self.refresh_prompt_categories()
        self.prompt_listbox.bind("<Double-Button-1>", self.copy_prompt_to_clipboard)
        self.prompt_listbox.bind("<Button-3>", lambda e: self.remove_item(e, "prompt"))

    def setup_settings_ui(self):
        hdr = tk.Frame(self.settings_frame, bg="#2a2c3a")
        hdr.pack(fill="x", side="top", padx=2, pady=2)
        
        lbl_st = tk.Label(hdr, text="⚙️ CÀI ĐẶT & TỐI ƯU HỆ THỐNG", bg="#2a2c3a", fg="#ffffff", font=("Segoe UI", 8, "bold"))
        lbl_st.pack(side="left", padx=5, pady=4)

        content = tk.Frame(self.settings_frame, bg="#1e1f29")
        content.pack(fill="both", expand=True, padx=10, pady=5)

        btn_ram = tk.Button(content, text="🚀 EMPTY RAM CACHE (RAMMap)", bg="#ff4d4f", fg="#ffffff", font=("Segoe UI", 8, "bold"), bd=0, command=self.empty_ram_cache)
        btn_ram.pack(fill="x", pady=(0, 6))

        lbl_cust = tk.Label(content, text="Thư mục xóa tùy chỉnh thêm:", bg="#1e1f29", fg="#ffb703", font=("Segoe UI", 8, "bold"))
        lbl_cust.pack(anchor="w")

        f_tools = tk.Frame(content, bg="#1e1f29")
        f_tools.pack(fill="x", pady=2)

        btn_add_folder = tk.Button(f_tools, text="+ Thêm thư mục", bg="#3b3e54", fg="white", bd=0, font=("Segoe UI", 8), command=self.add_custom_folder)
        btn_add_folder.pack(side="left")

        self.custom_folder_listbox = tk.Listbox(content, bg="#14151d", fg="#e0e0e0", bd=0, height=3, font=("Segoe UI", 8))
        self.custom_folder_listbox.pack(fill="both", expand=True, pady=2)
        self.custom_folder_listbox.bind("<Button-3>", self.remove_custom_folder)
        self.refresh_custom_folders()

    def empty_ram_cache(self):
        dlg = CustomConfirm(self.root, "Xóa Standby List & Working Sets của RAM?")
        self.root.wait_window(dlg)
        if dlg.result:
            try:
                cmd = 'powershell -command "[System.GC]::Collect(); [System.GC]::WaitForPendingFinalizers()"'
                subprocess.run(cmd, shell=True)
                messagebox.showinfo("Thành công", "⚡ Đã tối ưu và giải phóng RAM Cache!")
            except Exception as e:
                messagebox.showerror("Lỗi", f"Không thể giải phóng RAM: {str(e)}")

    def add_custom_folder(self):
        folder = filedialog.askdirectory(title="Chọn thư mục muốn dọn dẹp")
        if folder:
            f_norm = os.path.normpath(folder)
            cfgs = self.cfg.get("custom_folders", [])
            if f_norm not in cfgs:
                cfgs.append(f_norm)
                self.cfg["custom_folders"] = cfgs
                save_cfg(self.cfg)
                self.refresh_custom_folders()

    def refresh_custom_folders(self):
        self.custom_folder_listbox.delete(0, tk.END)
        for f in self.cfg.get("custom_folders", []):
            self.custom_folder_listbox.insert(tk.END, f" 📁 {f}")

    def remove_custom_folder(self, event):
        idx = self.custom_folder_listbox.nearest(event.y)
        cfgs = self.cfg.get("custom_folders", [])
        if 0 <= idx < len(cfgs):
            dlg = CustomConfirm(self.root, f"Xóa thư mục '{cfgs[idx]}' khỏi danh sách?")
            self.root.wait_window(dlg)
            if dlg.result:
                del cfgs[idx]
                self.cfg["custom_folders"] = cfgs
                save_cfg(self.cfg)
                self.refresh_custom_folders()

    def add_category(self, cat_type):
        def save_cat():
            name = entry.get().strip()
            if name:
                key = f"{cat_type}_data"
                if name not in self.cfg[key]:
                    self.cfg[key][name] = []
                    save_cfg(self.cfg)
                    if cat_type == "clip": self.refresh_clip_categories()
                    elif cat_type == "sfx": self.refresh_sfx_categories()
                    elif cat_type == "prompt": self.refresh_prompt_categories()
            top.destroy()

        top = tk.Toplevel(self.root)
        top.overrideredirect(True)
        top.attributes("-topmost", True)
        top.configure(bg="#1e1f29")
        pw, ph = self.root.winfo_width(), self.root.winfo_height()
        px, py = self.root.winfo_x(), self.root.winfo_y()
        top.geometry(f"220x90+{px + (pw-220)//2}+{py + (ph-90)//2}")

        tk.Label(top, text="Tên nhóm mới:", bg="#1e1f29", fg="#ffffff", font=("Segoe UI", 8, "bold")).pack(pady=4)
        entry = tk.Entry(top, bg="#14151d", fg="#ffffff", bd=1)
        entry.pack(padx=10, pady=2)
        entry.focus_set()

        tk.Button(top, text="Thêm", bg="#52c41a", fg="white", bd=0, command=save_cat).pack(pady=4)

    def refresh_clip_categories(self):
        cats = list(self.cfg.get("clip_data", {}).keys())
        if "Tất cả" not in cats: cats.insert(0, "Tất cả")
        self.clip_cat_cb['values'] = cats
        self.refresh_clip_listbox()

    def refresh_sfx_categories(self):
        cats = list(self.cfg.get("sfx_data", {}).keys())
        if "Tất cả" not in cats: cats.insert(0, "Tất cả")
        self.sfx_cat_cb['values'] = cats
        self.refresh_sfx_listbox()

    def refresh_prompt_categories(self):
        cats = list(self.cfg.get("prompt_data", {}).keys())
        self.prompt_cat_cb['values'] = cats
        if cats and self.prompt_cat_var.get() not in cats:
            self.prompt_cat_var.set(cats[0])
        self.refresh_prompt_listbox()

    def refresh_clip_listbox(self):
        self.clip_listbox.delete(0, tk.END)
        cat = self.clip_cat_var.get()
        clip_data = self.cfg.get("clip_data", {})
        
        paths = []
        if cat == "Tất cả":
            for p_list in clip_data.values(): paths.extend(p_list)
        else:
            paths = clip_data.get(cat, [])

        self.current_clips = list(set(paths))
        for p in self.current_clips:
            self.clip_listbox.insert(tk.END, f" 🎬 {os.path.basename(p)}")

    def refresh_sfx_listbox(self):
        self.sfx_listbox.delete(0, tk.END)
        cat = self.sfx_cat_var.get()
        sfx_data = self.cfg.get("sfx_data", {})
        
        paths = []
        if cat == "Tất cả":
            for p_list in sfx_data.values(): paths.extend(p_list)
        else:
            paths = sfx_data.get(cat, [])

        self.current_sfx = list(set(paths))
        for p in self.current_sfx:
            self.sfx_listbox.insert(tk.END, f" 🔊 {os.path.basename(p)}")

    def refresh_prompt_listbox(self):
        self.prompt_listbox.delete(0, tk.END)
        cat = self.prompt_cat_var.get()
        prompts = self.cfg.get("prompt_data", {}).get(cat, [])
        for p in prompts:
            self.prompt_listbox.insert(tk.END, f" 💡 {p.get('title', 'Untitled')}")

    def add_clip_files(self):
        files = filedialog.askopenfilenames(title="Chọn Clips/Media", filetypes=[("Media", "*.mp4 *.mov *.avi *.png *.jpg")])
        if files:
            cat = self.clip_cat_var.get()
            if cat == "Tất cả": cat = "Chung"
            data = self.cfg.get("clip_data", {})
            if cat not in data: data[cat] = []
            for f in files:
                p = os.path.normpath(f)
                if p not in data[cat]: data[cat].append(p)
            self.cfg["clip_data"] = data
            save_cfg(self.cfg)
            self.refresh_clip_listbox()

    def add_sfx_files(self):
        files = filedialog.askopenfilenames(title="Chọn SFX", filetypes=[("Audio", "*.mp3 *.wav *.ogg *.m4a")])
        if files:
            cat = self.sfx_cat_var.get()
            if cat == "Tất cả": cat = "Chung"
            data = self.cfg.get("sfx_data", {})
            if cat not in data: data[cat] = []
            for f in files:
                p = os.path.normpath(f)
                if p not in data[cat]: data[cat].append(p)
            self.cfg["sfx_data"] = data
            save_cfg(self.cfg)
            self.refresh_sfx_listbox()

    def add_prompt_item(self):
        def save_p():
            t = e_title.get().strip()
            c = txt_content.get("1.0", tk.END).strip()
            if t and c:
                cat = self.prompt_cat_var.get()
                p_data = self.cfg.get("prompt_data", {})
                if cat not in p_data: p_data[cat] = []
                p_data[cat].append({"title": t, "content": c})
                self.cfg["prompt_data"] = p_data
                save_cfg(self.cfg)
                self.refresh_prompt_listbox()
                top.destroy()

        top = tk.Toplevel(self.root)
        top.overrideredirect(True)
        top.attributes("-topmost", True)
        top.configure(bg="#1e1f29")
        pw, ph = self.root.winfo_width(), self.root.winfo_height()
        px, py = self.root.winfo_x(), self.root.winfo_y()
        top.geometry(f"300x200+{px + (pw-300)//2}+{py + (ph-200)//2}")

        tk.Label(top, text="Tiêu đề Prompt (Ngắn):", bg="#1e1f29", fg="#ffffff", font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=10, pady=(6,0))
        e_title = tk.Entry(top, bg="#14151d", fg="#ffffff", bd=1)
        e_title.pack(fill="x", padx=10, pady=2)

        tk.Label(top, text="Nội dung Prompt đầy đủ:", bg="#1e1f29", fg="#ffffff", font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=10, pady=(4,0))
        txt_content = tk.Text(top, bg="#14151d", fg="#ffffff", bd=1, height=4)
        txt_content.pack(fill="both", expand=True, padx=10, pady=2)

        tk.Button(top, text="Lưu Prompt", bg="#52c41a", fg="white", bd=0, font=("Segoe UI", 8, "bold"), command=save_p).pack(pady=6)

    def copy_prompt_to_clipboard(self, event):
        idx = self.prompt_listbox.nearest(event.y)
        cat = self.prompt_cat_var.get()
        prompts = self.cfg.get("prompt_data", {}).get(cat, [])
        if 0 <= idx < len(prompts):
            content = prompts[idx].get("content", "")
            self.root.clipboard_clear()
            self.root.clipboard_append(content)
            messagebox.showinfo("Thành công", f"⚡ Đã Copy Prompt '{prompts[idx]['title']}' vào bộ nhớ tạm!")

    def on_sfx_click_and_drag(self, event):
        idx = self.sfx_listbox.nearest(event.y)
        if 0 <= idx < len(getattr(self, 'current_sfx', [])):
            file_path = self.current_sfx[idx]
            self.drag_file_path = file_path
            set_clipboard_files([file_path])
            
            if HAS_PYGAME and os.path.exists(file_path):
                try:
                    pygame.mixer.music.load(file_path)
                    pygame.mixer.music.play()
                except Exception:
                    pass

    def on_drag_start(self, event, target_type):
        lbox = self.clip_listbox if target_type == "clip" else self.sfx_listbox
        arr = getattr(self, 'current_clips' if target_type == "clip" else 'current_sfx', [])
        idx = lbox.nearest(event.y)
        if 0 <= idx < len(arr):
            self.drag_file_path = arr[idx]
            set_clipboard_files([self.drag_file_path])

    def on_dragging(self, event):
        if hasattr(self, 'drag_file_path') and self.drag_file_path:
            self.root.config(cursor="hand2")

    def on_drag_end(self, event):
        self.root.config(cursor="")
        self.drag_file_path = None

    def remove_item(self, event, target_type):
        if target_type == "clip":
            lbox, cat = self.clip_listbox, self.clip_cat_var.get()
            key, arr = "clip_data", getattr(self, 'current_clips', [])
        elif target_type == "sfx":
            lbox, cat = self.sfx_listbox, self.sfx_cat_var.get()
            key, arr = "sfx_data", getattr(self, 'current_sfx', [])
        else:
            lbox, cat = self.prompt_listbox, self.prompt_cat_var.get()
            key, arr = "prompt_data", self.cfg.get("prompt_data", {}).get(cat, [])

        idx = lbox.nearest(event.y)
        if 0 <= idx < len(arr):
            dlg = CustomConfirm(self.root, "Xóa mục này khỏi danh sách?")
            self.root.wait_window(dlg)
            if dlg.result:
                if target_type == "prompt":
                    del self.cfg[key][cat][idx]
                else:
                    target_path = arr[idx]
                    if cat == "Tất cả":
                        for c in self.cfg[key]:
                            if target_path in self.cfg[key][c]: self.cfg[key][c].remove(target_path)
                    else:
                        if target_path in self.cfg[key][cat]: self.cfg[key][cat].remove(target_path)

                save_cfg(self.cfg)
                if target_type == "clip": self.refresh_clip_listbox()
                elif target_type == "sfx": self.refresh_sfx_listbox()
                else: self.refresh_prompt_listbox()

    def toggle_visibility_animated(self, event=None):
        if self.animating: return
        self.animating = True
        
        cur_x = self.root.winfo_x()
        cur_y = self.root.winfo_y()

        if not self.is_hidden:
            for i in range(0, 10):
                self.root.geometry(f"+{cur_x}+{cur_y + i*5}")
                self.root.attributes("-alpha", 1.0 - (i * 0.09))
                self.root.update()
                self.root.after(10)
            self.root.withdraw()
            self.is_hidden = True
        else:
            self.root.deiconify()
            for i in range(10, -1, -1):
                self.root.geometry(f"+{cur_x}+{cur_y + i*5}")
                self.root.attributes("-alpha", 1.0 - (i * 0.09))
                self.root.update()
                self.root.after(10)
            self.is_hidden = False

        self.animating = False

    def draw_ui(self):
        self.canvas.delete("all")
        w, h = self.root.winfo_width(), self.root.winfo_height()
        if w < 10 or h < 10: return

        self.draw_rounded_rect(3, 3, w - 3, h - 3, radius=16, fill="#1e1f29", outline="#3b3e54", width=1.5)
        self.draw_rounded_rect(5, 5, w - 5, max(10, 38), radius=12, fill="#2a2c3a", outline="", width=0)

        dot_color = "#ff4d4f" if self.locked else "#52c41a"
        self.lock_dot = self.canvas.create_oval(14, 14, 24, 24, fill=dot_color, outline="#ffffff", width=1)
        self.canvas.tag_bind(self.lock_dot, "<Button-1>", self.toggle_lock)

        tabs = [("clips", "🎬 CLIPS", 32, 92), ("sfx", "🎵 SFX", 97, 152), ("prompts", "💡 PROMPT", 157, 232), ("settings", "⚙️ SETTINGS", 237, 312)]
        for name, text, x1, x2 in tabs:
            bg = "#ffb703" if self.active_panel == name else "#2b2d42"
            fg = "#000000" if self.active_panel == name else "#ffffff"
            r = self.draw_rounded_rect(x1, 10, x2, 34, radius=6, fill=bg, outline="#4a4d6b")
            t = self.canvas.create_text((x1 + x2)//2, 22, text=text, fill=fg, font=("Segoe UI", 8, "bold"))
            for el in [r, t]: self.canvas.tag_bind(el, "<Button-1>", lambda e, n=name: self.toggle_panel(n))

        btn_close_r = self.draw_rounded_rect(w - 30, 10, w - 10, 34, radius=6, fill="#2b2d42", outline="#4a4d6b")
        btn_close_t = self.canvas.create_text(w - 20, 22, text="✕", fill="#ffffff", font=("Segoe UI", 8, "bold"))
        for el in [btn_close_r, btn_close_t]: self.canvas.tag_bind(el, "<Button-1>", self.quit_app)

        btn_text_str = "⏳ WORKING..." if self.is_cleaning else "🧹 CLEAR ALL CACHE"
        btn_fill = "#212333" if (self.locked or self.is_cleaning) else "#2b2d42"
        
        btn_h_bottom = (h - 220) if self.active_panel else (h - 10)
        self.btn_clear_rect = self.draw_rounded_rect(10, 42, w - 10, max(75, btn_h_bottom), radius=10, fill=btn_fill, outline="#4a4d6b")
        self.btn_clear_txt = self.canvas.create_text(w // 2, 42 + (max(75, btn_h_bottom) - 42) // 2, text=btn_text_str, fill="#ffffff", font=("Segoe UI", 9, "bold"))

        if not self.is_cleaning:
            for el in [self.btn_clear_rect, self.btn_clear_txt]:
                self.canvas.tag_bind(el, "<Button-1>", self.on_clear_click)

        if not self.locked:
            self.grip = self.canvas.create_polygon(w - 18, h - 4, w - 4, h - 18, w - 4, h - 4, fill="#ffb703", outline="")

    def toggle_panel(self, panel_name):
        self.clips_frame.place_forget()
        self.sfx_frame.place_forget()
        self.prompts_frame.place_forget()
        self.settings_frame.place_forget()

        if self.active_panel == panel_name:
            self.active_panel = None
            self.root.geometry(f'{self.root.winfo_width()}x90')
        else:
            self.active_panel = panel_name
            self.root.geometry(f'{self.root.winfo_width()}x320')
            w = self.root.winfo_width() - 20
            h = 220
            if panel_name == "clips": self.clips_frame.place(x=10, y=85, width=w, height=h)
            elif panel_name == "sfx": self.sfx_frame.place(x=10, y=85, width=w, height=h)
            elif panel_name == "prompts": self.prompts_frame.place(x=10, y=85, width=w, height=h)
            elif panel_name == "settings": self.settings_frame.place(x=10, y=85, width=w, height=h)

        self.draw_ui()

    def on_canvas_press(self, e):
        if self.locked: return
        w, h = self.root.winfo_width(), self.root.winfo_height()
        if (w - 22 <= e.x <= w) and (h - 22 <= e.y <= h):
            self.is_resizing = True
            self.start_rw, self.start_rh = w, h
            self.start_rx, self.start_ry = e.x_root, e.y_root
        else:
            self.is_resizing = False
            self.mx, self.my = e.x_root, e.y_root

    def on_canvas_drag(self, e):
        if self.locked: return
        if getattr(self, 'is_resizing', False):
            new_w = max(400, self.start_rw + (e.x_root - self.start_rx))
            min_h = 320 if self.active_panel else 90
            new_h = max(min_h, self.start_rh + (e.y_root - self.start_ry))
            self.root.geometry(f"{new_w}x{new_h}")
        else:
            dx = e.x_root - self.mx
            dy = e.y_root - self.my
            self.mx, self.my = e.x_root, e.y_root
            self.root.geometry(f"+{self.root.winfo_x() + dx}+{self.root.winfo_y() + dy}")

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
        dlg = CustomConfirm(self.root, "Xóa toàn bộ Cache CapCut & các thư mục đã thêm?")
        self.root.wait_window(dlg)
        if dlg.result:
            self.is_cleaning = True
            self.draw_ui()
            threading.Thread(target=self.run_clear_logic, daemon=True).start()

    def run_clear_logic(self):
        target_paths = []
        for cat in CACHE_CATEGORIES.values(): target_paths.extend(cat["paths"])
        target_paths.extend(self.cfg.get("custom_folders", []))

        success_count = 0
        for folder_path in target_paths:
            if os.path.exists(folder_path):
                try:
                    shutil.rmtree(folder_path, onerror=remove_readonly)
                    success_count += 1
                except Exception:
                    pass

        def done():
            messagebox.showinfo("Hoàn tất", f"✨ Đã làm sạch {success_count} thư mục Cache!")
            self.is_cleaning = False
            self.draw_ui()

        self.root.after(0, done)

    def on_resize(self, e):
        w = self.root.winfo_width() - 20
        h = self.root.winfo_height() - 95
        if self.active_panel == "clips": self.clips_frame.place(x=10, y=85, width=w, height=h)
        elif self.active_panel == "sfx": self.sfx_frame.place(x=10, y=85, width=w, height=h)
        elif self.active_panel == "prompts": self.prompts_frame.place(x=10, y=85, width=w, height=h)
        elif self.active_panel == "settings": self.settings_frame.place(x=10, y=85, width=w, height=h)
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
