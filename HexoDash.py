# -*- coding: utf-8 -*-
"""
HexoDash - 220x230 1.0.2
一个用于Hexo博客的GUI命令助手，
通过GUI页面快速完成新建文章、运行生成、部署和预览等常用操作。
免去开终端输入命令的麻烦。

附带尾部参数大全表。
2025.10.03 19:29:03
"""

import os, sys, threading, subprocess, signal, tempfile, shutil, re, locale
import tkinter as Tk
from tkinter import messagebox, scrolledtext
from tkinter import font as tkfont
from tkinter import ttk

# =============== 可调常量（布局的像素/字体调整） ===============
WinW, WinH       = 220, 230                     # 主窗口尺寸
FontMain         = ("Adobe Song Std L", 11)     # 标签、输入框字体
EntryWidthPx     = 92                           # 输入框宽
EntryHeightPx    = 22                           # 输入框高
EntryYOffset     = 0                            # 输入框Y微调（垂直居中）

# 输入框防粘边
EntryInnerPadding = (3, 1, 3, 1)                # (左,上,右,下)

# 新建区，新建文章、草稿、页面
LblX, EntX       = 16, 100                      # 左侧文字X / 右列输入框X
RowY0, RowStep   = 10, 28                       # 第一行Y / 行间距
SepY             = RowY0 + RowStep * 3 + 6      # 分割线Y
SepDashLen       = 4                            # 虚线线段长度

# 组合命令区，勾选运行命令
CkY1, CkY2       = SepY + 16, SepY + 40
CkLblL_X, CkBoxL_X = 16, 96                     # 第一列文字X / 小方框X
CkLblR_X, CkBoxR_X = 118, 188                   # 第二列文字X / 小方框X
CkTextYOffset    = 0                            # 勾选项文字Y轴微调
CkBoxYOffset     = 1                            # 勾选框相对文字Y微调

# 运行部分，尾部参数、安装Hexo、运行命令
TailLblX         = 14                           # 尾部参数文字X
TailY            = CkY2 + 24                    # 尾部参数Y
TailYOffset      = 2                            # 尾部参数输入框Y
TailEntX         = 86                           # 尾部参数输入框X
TailEntW, TailEntH = 96, 22                     # 尾部参数输入框宽 / 高
InfoBtnSize      = 18                           # 尾部参数信息按钮尺寸

BtnY, BtnW, BtnH = WinH - 36, 78, 26            # 底部按钮Y/宽/高
BtnLeftX, BtnRightX = 14, WinW - 14 - BtnW      # 左右按钮X

# 终端窗口（黑底 & 保留颜色码渲染）
TermFontFamily     = "Lucida Console"           # 终端字体
TermFontSize       = 9                          # 终端字号
TermBg             = "#000000"                  # 终端背景（黑色）
TermDefaultFg      = "#E6E6E6"                  # 默认前景（浅灰）
TermNew_W,   TermNew_H   = 220, 85              # 新建功能终端
TermCombo_W, TermCombo_H = 400, 250             # 组合命令终端
TermLive_W,  TermLive_H  = 400, 250             # 实时终端

# =============== 图标资源路径 ===============
def ResourcePath(rel_path: str) -> str:
    try:
        base = sys._MEIPASS  # type: ignore[attr-defined]
    except Exception:
        base = os.path.abspath(".")
    return os.path.join(base, rel_path)

def SetupIcon(win: Tk.Misc, ico_name: str = "Hexo.ico"):
    try:
        src = ResourcePath(ico_name)
        tmp = tempfile.gettempdir()
        dst = os.path.join(tmp, f"HexoDash_icon_{os.getpid()}.ico")
        if not os.path.exists(dst) or os.path.getmtime(src) > os.path.getmtime(dst):
            shutil.copy2(src, dst)
        win.iconbitmap(dst)
    except Exception as e:
        print(f"警告：设置窗口图标失败，将使用默认图标。原因：{e}")

# =============== 子进程（静默） ===============
def AppDir() -> str:
    try: return os.path.dirname(os.path.abspath(sys.argv[0])) or os.getcwd()
    except Exception: return os.getcwd()
BaseDir = AppDir()

def SilentPopen(cmd: str, new_group: bool = False) -> subprocess.Popen:
    """静默启动一个子进程（不显示终端窗口）。支持在 Linux/macOS 上创建新的进程组以便终止。"""
    creation_flags = 0
    startupinfo = None
    preexec_fn = None
    if os.name == "nt":
        creation_flags |= getattr(subprocess, "CREATE_NO_WINDOW", 0)
        if new_group:
            creation_flags |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    else:
        if new_group:
            preexec_fn = os.setsid
    return subprocess.Popen(
        cmd, shell=True, cwd=BaseDir,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        startupinfo=startupinfo, creationflags=creation_flags, preexec_fn=preexec_fn
    )

def _decode_best(b: bytes) -> str:
    """按常见编码顺序尝试解码，修复中文乱码；不丢颜色码。"""
    if not isinstance(b, (bytes, bytearray)):
        return str(b)
    for enc in ("utf-8", "utf-8-sig", "gb18030", "gbk", (locale.getpreferredencoding(False) or "utf-8")):
        try:
            return b.decode(enc)
        except Exception:
            pass
    return b.decode("utf-8", errors="replace")

def RunShell(cmd: str) -> tuple[int, str]:
    p = SilentPopen(cmd)
    out, _ = p.communicate()
    return p.returncode, _decode_best(out or b"")

# =============== ANSI颜色渲染 ===============
_ansi_pat = re.compile(r'\x1b\[([0-9;]*)m')

ANSI_FG = {
    30:"#000000", 31:"#CD3131", 32:"#0DBC79", 33:"#E5E510",
    34:"#2472C8", 35:"#BC3FBC", 36:"#11A8CD", 37:"#E5E5E5",
    90:"#666666", 91:"#F14C4C", 92:"#23D18B", 93:"#F5F543",
    94:"#3B8EEA", 95:"#D670D6", 96:"#29B8DB", 97:"#FFFFFF",
}
ANSI_BG = {
    40:"#000000", 41:"#CD3131", 42:"#0DBC79", 43:"#E5E510",
    44:"#2472C8", 45:"#BC3FBC", 46:"#11A8CD", 47:"#E5E5E5",
    100:"#666666", 101:"#F14C4C", 102:"#23D18B", 103:"#F5F543",
    104:"#3B8EEA", 105:"#D670D6", 106:"#29B8DB", 107:"#FFFFFF",
}

def _ensure_tag(txt: Tk.Text, name: str, **cfg):
    try:
        txt.tag_config(name)
    except Exception:
        pass
    txt.tag_config(name, **cfg)

def setup_ansi_tags(txt: Tk.Text):
    txt.configure(bg=TermBg, fg=TermDefaultFg,
                  insertbackground=TermDefaultFg,
                  font=(TermFontFamily, TermFontSize))
    _ensure_tag(txt, "fg_default", foreground=TermDefaultFg)
    _ensure_tag(txt, "bg_default", background=TermBg)
    _ensure_tag(txt, "bold_on", font=(TermFontFamily, TermFontSize, "bold"))
    _ensure_tag(txt, "ul_on", underline=1)
    for code, col in ANSI_FG.items():
        _ensure_tag(txt, f"fg_{code}", foreground=col)
    for code, col in ANSI_BG.items():
        _ensure_tag(txt, f"bg_{code}", background=col)

def insert_ansi(txt: Tk.Text, s: str, st: dict):
    pos = 0
    for m in _ansi_pat.finditer(s):
        if m.start() > pos:
            seg = s[pos:m.start()]
            tags = [st["fg"], st["bg"]]
            if st["bold"]: tags.append("bold_on")
            if st["ul"]:   tags.append("ul_on")
            txt.insert("end", seg, tuple(tags))
        params = m.group(1)
        if params == "" or params == "0":
            st.update(fg="fg_default", bg="bg_default", bold=False, ul=False)
        else:
            for p in (int(x) if x else 0 for x in params.split(";")):
                if p == 0: st.update(fg="fg_default", bg="bg_default", bold=False, ul=False)
                elif p == 1: st["bold"] = True
                elif p == 22: st["bold"] = False
                elif p == 4: st["ul"] = True
                elif p == 24: st["ul"] = False
                elif p in ANSI_FG: st["fg"] = f"fg_{p}"
                elif p in ANSI_BG: st["bg"] = f"bg_{p}"
                elif p == 39: st["fg"] = "fg_default"
                elif p == 49: st["bg"] = "bg_default"
        pos = m.end()
    if pos < len(s):
        seg = s[pos:]
        tags = [st["fg"], st["bg"]]
        if st["bold"]: tags.append("bold_on")
        if st["ul"]:   tags.append("ul_on")
        txt.insert("end", seg, tuple(tags))

def terminal_popup(parent: Tk.Misc, title: str, content: str, w: int, h: int):
    """黑底、支持颜色码的结果弹窗（尺寸可传入）。"""
    win = Tk.Toplevel(parent)
    SetupIcon(win, "Hexo.ico")
    win.title(title); win.geometry(f"{w}x{h}"); win.transient(parent); win.grab_set()
    txt = scrolledtext.ScrolledText(win, wrap="word")
    txt.pack(fill="both", expand=True, padx=10, pady=(10))
    setup_ansi_tags(txt)
    state = {"fg": "fg_default", "bg": "bg_default", "bold": False, "ul": False}
    insert_ansi(txt, content, state)
    txt.configure(state="disabled")

# =============== 弹窗 ===============
def PopupText(parent: Tk.Misc, title: str, content: str):
    win = Tk.Toplevel(parent)
    SetupIcon(win, "Hexo.ico")
    LargeFont = tkfont.Font(family="Microsoft YaHei UI", size=12)
    win.title(title); win.geometry("330x430"); win.transient(parent); win.grab_set()
    txt = scrolledtext.ScrolledText(win, wrap="word", font=LargeFont)
    txt.pack(fill="both", expand=True, padx=10, pady=(10))
    txt.insert("1.0", content); txt.configure(state="disabled")

# =============== Tooltip ===============
class Tooltip:
    def __init__(self, widget: Tk.Misc, text: str):
        self.widget = widget
        self.text = text
        self.tip = None
        widget.bind("<Enter>", self.show)
        widget.bind("<Leave>", self.hide)
        widget.bind("<Button-1>", self.hide)
    def show(self, _=None):
        if self.tip is not None: return
        x = self.widget.winfo_rootx() + self.widget.winfo_width()//2
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 10
        self.tip = Tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.attributes("-topmost", True)
        lbl = Tk.Label(self.tip, text=self.text, bg="#111", fg="#fff",
                       padx=8, pady=5, relief="solid", bd=1,
                       font=("Adobe Song Std L", 9))
        lbl.pack()
        self.tip.geometry(f"+{x}+{y}")
    def hide(self, _=None):
        if self.tip is not None:
            try: self.tip.destroy()
            except Exception: pass
            self.tip = None

# =============== 实时终端 ===============
class LiveTerm:
    """实时终端窗口滚动显示输出；Ctrl+C/关闭结束后回调 OnFinish(rc, out)
       备注：用户主动关闭（点X或“停止/Ctrl+C”）不弹出任何完成/错误提示。"""
    def __init__(self, root: Tk.Tk, cmd: str, title: str, on_finish):
        self.Root, self.Cmd, self.OnFinish = root, cmd, on_finish
        self.Buf = []
        self.Aborted = False  # 主动终止标记

        self.Win = Tk.Toplevel(root)
        self.Win.title(title); self.Win.geometry(f"{TermLive_W}x{TermLive_H}"); self.Win.transient(root)
        self.Txt = scrolledtext.ScrolledText(self.Win, wrap="word")
        self.Txt.pack(fill="both", expand=True, padx=10, pady=(10,0))
        setup_ansi_tags(self.Txt)

        bar = Tk.Frame(self.Win); bar.pack(fill="x", padx=10, pady=8)
        Tk.Button(bar, text="停止（Ctrl+C）", command=self.Stop).pack(side="left")
        Tk.Button(bar, text="复制全部", command=self.CopyAll).pack(side="left", padx=(8,0))
        self.Win.bind("<Control-c>", lambda e: self.Stop())
        self.Win.protocol("WM_DELETE_WINDOW", self.Stop)

        self.Proc = SilentPopen(self.Cmd, new_group=True)
        self.State = {"fg": "fg_default", "bg": "bg_default", "bold": False, "ul": False}
        threading.Thread(target=self.ReadLoop, daemon=True).start()
        threading.Thread(target=self.WaitLoop, daemon=True).start()

    def Append(self, s: str):
        if isinstance(s, (bytes, bytearray)):
            s = _decode_best(s)
        insert_ansi(self.Txt, s, self.State)
        self.Buf.append(s)
        self.Txt.see("end")

    def ReadLoop(self):
        try:
            while True:
                if self.Proc.stdout is None: break
                line = self.Proc.stdout.readline()
                if not line: break
                self.Root.after(0, self.Append, line)
        except Exception as e:
            self.Root.after(0, self.Append, f"\n[读取输出异常] {e}\n")

    def WaitLoop(self):
        rc = self.Proc.wait()
        out_bytes = b"".join([x.encode("utf-8", "replace") if isinstance(x, str) else x for x in []])  # 占位（已在读循环累计到 Buf）
        out = "".join(self.Buf)
        def Done():
            try: self.Win.destroy()
            except Exception: pass
            if not self.Aborted:
                self.OnFinish(rc, out)
        self.Root.after(0, Done)

    def Stop(self):
        self.Aborted = True  # 主动终止
        try:
            if os.name != "nt":
                try: os.killpg(self.Proc.pid, signal.SIGINT)
                except Exception: self.Proc.terminate()
            else:
                try: self.Proc.terminate()
                except Exception: pass
                try:
                    subprocess.run(f'taskkill /PID {self.Proc.pid} /T /F', shell=True, cwd=BaseDir,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                   creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
                except Exception: pass
        except Exception: pass

    def CopyAll(self):
        txt = "".join(self.Buf)
        self.Root.clipboard_clear(); self.Root.clipboard_append(txt)
        Tk.messagebox.showinfo("已复制", "已复制全部运行输出。", parent=self.Win)

# =============== 主程序 ===============
class HexoDashApp:
    """
    HexoDash 主应用类。
    负责构建主窗口 UI、绑定控件事件、处理变量以及管理命令的构建和执行。
    """
    def __init__(self, root: Tk.Tk):
        self.Root = root
        root.title("HexoDash"); root.geometry(f"{WinW}x{WinH}"); root.resizable(False, False)
        SetupIcon(root, "Hexo.ico")
        root.update_idletasks()

        # 变量
        self.PostVar   = Tk.StringVar(root)
        self.DraftVar  = Tk.StringVar(root)
        self.PageVar   = Tk.StringVar(root)
        self.GenVar    = Tk.BooleanVar(root, False)
        self.DeployVar = Tk.BooleanVar(root, False)
        self.ServerVar = Tk.BooleanVar(root, False)
        self.CleanVar  = Tk.BooleanVar(root, False)
        self.TailVar   = Tk.StringVar(root)

        # 防粘边
        self.Style = ttk.Style(root)
        self.Style.configure("Dash.TEntry", padding=EntryInnerPadding)
        self.BuildUi()

        # 双向置灰
        self._MutualLock = False
        self.ServerVar.trace_add("write", self.OnServerChange)
        self.DeployVar.trace_add("write", self.OnDeployChange)

    # ---------- 组合命令区 ----------
    def PlaceRightCheck(self, text: str, var: Tk.BooleanVar, lx: int, bx: int, y: int):
        lbl = Tk.Label(self.Root, text=text, font=FontMain, cursor="hand2")
        lbl.place(x=lx, y=y + CkTextYOffset)

        chk = Tk.Checkbutton(self.Root, variable=var, bd=0, highlightthickness=0,
                             padx=0, pady=0, text="", width=0, takefocus=False)
        chk.place(x=bx, y=y + CkBoxYOffset)

        def toggle(_=None):
            if str(chk.cget("state")) == "disabled":
                return
            var.set(not var.get())
        lbl.bind("<Button-1>", toggle)

        return lbl, chk

    # ------- UI -------
    def BuildUi(self):
        r = self.Root
        Tk.Label(r, text="新建文章", font=FontMain).place(x=LblX, y=RowY0)
        ttk.Entry(r, textvariable=self.PostVar, font=FontMain, style="Dash.TEntry")\
            .place(x=EntX, y=RowY0 + EntryYOffset, width=EntryWidthPx, height=EntryHeightPx)

        Tk.Label(r, text="新建草稿", font=FontMain).place(x=LblX, y=RowY0+RowStep)
        ttk.Entry(r, textvariable=self.DraftVar, font=FontMain, style="Dash.TEntry")\
            .place(x=EntX, y=RowY0+RowStep + EntryYOffset, width=EntryWidthPx, height=EntryHeightPx)

        Tk.Label(r, text="新建页面", font=FontMain).place(x=LblX, y=RowY0+RowStep*2)
        ttk.Entry(r, textvariable=self.PageVar, font=FontMain, style="Dash.TEntry")\
            .place(x=EntX, y=RowY0+RowStep*2 + EntryYOffset, width=EntryWidthPx, height=EntryHeightPx)

        for child in r.place_slaves():
            if isinstance(child, ttk.Entry):
                child.bind("<Return>", lambda e: self.RunNewOnly())

        # 虚线
        dash = Tk.Canvas(r, width=WinW-16, height=2, highlightthickness=0)
        dash.place(x=8, y=SepY)
        for x in range(0, WinW-16, (SepDashLen*2)):
            dash.create_line(x, 1, x+SepDashLen, 1, fill="#888")

        # 组合命令勾选框
        self.GenLbl,    self.GenChk    = self.PlaceRightCheck("生成页面", self.GenVar,    CkLblL_X, CkBoxL_X, CkY1)
        self.DeployLbl, self.DeployChk = self.PlaceRightCheck("上传仓库", self.DeployVar, CkLblR_X, CkBoxR_X, CkY1)
        self.ServerLbl, self.ServerChk = self.PlaceRightCheck("运行预览", self.ServerVar, CkLblL_X, CkBoxL_X, CkY2)
        self.CleanLbl,  self.CleanChk  = self.PlaceRightCheck("清理缓存", self.CleanVar,  CkLblR_X, CkBoxR_X, CkY2)

        # 尾部参数
        Tk.Label(r, text="尾部参数", font=FontMain).place(x=TailLblX, y=TailY)
        ttk.Entry(r, textvariable=self.TailVar, font=FontMain, style="Dash.TEntry")\
            .place(x=TailEntX, y=TailY + TailYOffset, width=TailEntW, height=TailEntH)

        # Tooltip
        info = Tk.Label(r, text="ⓘ", font=("Segoe UI Symbol", 14), fg="#6b7280", cursor="hand2")
        info.place(x=TailEntX + TailEntW + 6, y=TailY + 1, width=InfoBtnSize, height=InfoBtnSize)
        Tooltip(info, "尾部参数大全")
        info.bind("<Button-1>", lambda e: self.ShowTailInfo())

        # 底部按钮
        Tk.Button(r, text="安装Hexo", command=self.InstallHexo, font=FontMain)\
            .place(x=BtnLeftX,  y=BtnY, width=BtnW, height=BtnH)
        Tk.Button(r, text="运行", command=self.RunAll, font=FontMain)\
            .place(x=BtnRightX, y=BtnY, width=BtnW, height=BtnH)

    # ------- 互斥切换 -------
    def _set_enabled(self, chk: Tk.Checkbutton, lbl: Tk.Label, enabled: bool):
        chk.configure(state="normal" if enabled else "disabled")
        lbl.configure(fg="black" if enabled else "#9e9e9e", cursor="hand2" if enabled else "arrow")

    def OnServerChange(self, *_):
        if getattr(self, "_MutualLock", False): return
        self._MutualLock = True
        try:
            if self.ServerVar.get():
                self.DeployVar.set(False)
                self._set_enabled(self.DeployChk, self.DeployLbl, False)
            else:
                self._set_enabled(self.DeployChk, self.DeployLbl, True)
        finally:
            self._MutualLock = False

    def OnDeployChange(self, *_):
        if getattr(self, "_MutualLock", False): return
        self._MutualLock = True
        try:
            if self.DeployVar.get():
                self.ServerVar.set(False)
                self._set_enabled(self.ServerChk, self.ServerLbl, False)
            else:
                self._set_enabled(self.ServerChk, self.ServerLbl, True)
        finally:
            self._MutualLock = False

    # ------- 辅助 -------
    def ShowTailInfo(self):
        info = (
            "Hexo 全局参数\n"
            "--config   自定义配置文件的路径\n"
            "--cwd      指定 Hexo 网站的根目录\n"
            "--debug    启用调试模式输出日志\n"
            "--draft    包含草稿文件生成页面\n"
            "--safe     安全模式不加载插件脚本\n"
            "--silent   静默运行隐藏输出信息\n\n"
            "New (新建)\n"
            "--path      自定义新建内容文件路径\n"
            "--replace   强制替换现有文件\n"
            "--slug      自定义文章 URL 部分\n\n"
            "Generate (生成)\n"
            "--deploy    生成完成后执行部署\n"
            "--watch     监听并自动重新生成\n"
            "--force     忽略文件缓存重新生成页面\n"
            "--bail      遇到未处理异常中止\n\n"
            "Deploy (部署)\n"
            "--generate  部署前先生成静态文件\n\n"
            "Server (服务器)\n"
            "--port      指定运行端口\n"
            "--host      指定运行IP\n"
            "--static    禁用监听文件变化\n"
            "--log       启用日志，输出事件信息"
        )
        PopupText(self.Root, "尾部参数大全", info)

    def AppendTailEach(self, seq: list[str]) -> list[str]:
        """给序列中每条命令都附加尾部参数（用于“新建”场景）。"""
        tail = self.TailVar.get().strip()
        if not tail: return seq
        return [f"{cmd} {tail}" for cmd in seq]

    def AppendTail(self, cmd: str) -> str:
        """仅给最后一条加尾巴（组合命令时保持你原有逻辑）"""
        tail = self.TailVar.get().strip()
        return f"{cmd} {tail}" if tail else cmd

    def BuildNewSeq(self) -> list[str]:
        seq = []
        p, d, g = self.PostVar.get().strip(), self.DraftVar.get().strip(), self.PageVar.get().strip()
        if p: seq.append(f'hexo new "{p}"')
        if d: seq.append(f'hexo new draft "{d}"')
        if g: seq.append(f'hexo new page "{g}"')
        if seq: self.PostVar.set(""); self.DraftVar.set(""); self.PageVar.set("")
        return seq

    def BuildComboSeq(self) -> list[str]:
        seq = []
        if self.CleanVar.get():  seq.append("hexo clean")
        if self.GenVar.get():    seq.append("hexo generate")
        if self.DeployVar.get(): seq.append("hexo deploy")
        if self.ServerVar.get(): seq.append("hexo server")
        return seq

    # ------- 回车运行 -------
    def RunNewOnly(self):
        new_seq = self.BuildNewSeq()
        if not new_seq:
            return
        cmds = " && ".join(self.AppendTailEach(new_seq))
        def Task():
            code, out = RunShell(cmds)
            self.Root.after(0, lambda: terminal_popup(self.Root, "完成" if code == 0 else "错误", out, TermNew_W, TermNew_H))
        threading.Thread(target=Task, daemon=True).start()

    # ------- 运行按钮 -------
    def RunAll(self):
        new_seq   = self.BuildNewSeq()
        combo_seq = self.BuildComboSeq()
        if not new_seq and not combo_seq:
            messagebox.showwarning("提示", "请先输入要新建的名称或勾选组合操作。", parent=self.Root)
            return

        if new_seq and not combo_seq:
            cmds = " && ".join(self.AppendTailEach(new_seq))
            def TaskNew():
                code, out = RunShell(cmds)
                self.Root.after(0, lambda: terminal_popup(self.Root, "完成" if code == 0 else "错误", out, TermNew_W, TermNew_H))
            threading.Thread(target=TaskNew, daemon=True).start()
            return

        full = new_seq + combo_seq
        is_server_last = (len(full) > 0 and full[-1].startswith("hexo server"))

        if is_server_last:
            head = full[:-1]
            server_cmd = self.AppendTail(full[-1])
            head_cmd = " && ".join(head) if head else None

            def RunHeadThenServer():
                if head_cmd:
                    code, out = RunShell(head_cmd)
                    if code != 0:
                        self.Root.after(0, lambda: terminal_popup(self.Root, "错误", out, TermCombo_W, TermCombo_H))
                        return
                def OnFinish(rc, out):
                    terminal_popup(self.Root, "完成" if rc == 0 else "错误", out, TermCombo_W, TermCombo_H)
                LiveTerm(self.Root, server_cmd, "预览终端（hexo server）", OnFinish)
            threading.Thread(target=RunHeadThenServer, daemon=True).start()
            return

        if len(full) == 1:
            cmd = self.AppendTail(full[0])
        else:
            last = self.AppendTail(full[-1])
            cmd = " && ".join(full[:-1] + [last])

        def TaskCombo():
            code, out = RunShell(cmd)
            self.Root.after(0, lambda: terminal_popup(self.Root, "完成" if code == 0 else "错误", out, TermCombo_W, TermCombo_H))
        threading.Thread(target=TaskCombo, daemon=True).start()

    def InstallHexo(self):
        chain = "npm install hexo-cli -g && hexo init blog && cd blog && npm install"
        def OnFinish(rc, out):
            terminal_popup(self.Root, "完成" if rc == 0 else "错误", out, TermCombo_W, TermCombo_H)
        LiveTerm(self.Root, chain, "安装 Hexo（实时输出）", OnFinish)

# 入口
def Main():
    root = Tk.Tk()
    app  = HexoDashApp(root)
    root.mainloop()

if __name__ == "__main__":
    Main()