# -*- coding: utf-8 -*-
"""
HexoDash - 220x230 1.0.0-rc.1
一个用于Hexo博客的GUI命令助手，
通过GUI页面快速完成新建文章、运行生成、部署和预览等常用操作。
免去开终端输入命令的麻烦。

附带尾部参数大全表。
2025.10.03 19:29:03
"""

import os, sys, threading, subprocess, signal, tempfile, shutil
import tkinter as Tk
from tkinter import messagebox, scrolledtext
from tkinter import font as tkfont

# =============== 可调常量（布局的像素/字体调整） ===============
WinW, WinH       = 220, 230                     # 主窗口尺寸
FontMain         = ("Microsoft YaHei UI", 11)   # 标签、输入框字体
EntryWidthPx     = 92
EntryHeightPx    = 22
EntryYOffset     = 2

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
CkBoxYOffset     = 3                            # 勾选框相对文字Y微调

# 运行部分，尾部参数、安装Hexo、运行命令
TailLblX         = 14                           # 尾部参数文字X
TailY            = CkY2 + 24                    # 尾部参数Y
TailYOffset      = 2                            # 尾部参数输入框Y
TailEntX         = 86                           # 尾部参数输入框X
TailEntW, TailEntH = 96, 22                     # 尾部参数输入框宽 / 高
InfoBtnSize      = 18                           # 尾部参数信息按钮尺寸

BtnY, BtnW, BtnH = WinH - 36, 78, 26
BtnLeftX, BtnRightX = 14, WinW - 14 - BtnW

# =============== 图标资源路径 ===============
def ResourcePath(rel_path: str) -> str:
    try:
        base = sys._MEIPASS  # type: ignore[attr-defined]
    except Exception:
        base = os.path.abspath(".")
    return os.path.join(base, rel_path)

def SetupIcon(root: Tk.Tk, ico_name: str = "Hexo.ico"):
    try:
        src = ResourcePath(ico_name)
        tmp = tempfile.gettempdir()
        dst = os.path.join(tmp, f"HexoDash_icon_{os.getpid()}.ico")
        if not os.path.exists(dst) or os.path.getmtime(src) > os.path.getmtime(dst):
            shutil.copy2(src, dst)
        root.iconbitmap(dst)
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
        text=True, encoding="utf-8", errors="replace",
        startupinfo=startupinfo, creationflags=creation_flags, preexec_fn=preexec_fn
    )

def RunShell(cmd: str) -> tuple[int, str]:
    p = SilentPopen(cmd)
    out, _ = p.communicate()
    return p.returncode, out

# =============== 弹窗与实时终端 ===============
def PopupText(parent: Tk.Misc, title: str, content: str):
    win = Tk.Toplevel(parent)
    SetupIcon(win, "Hexo.ico")
    LargeFont = tkfont.Font(family="Microsoft YaHei UI", size=12)
    win.title(title); win.geometry("330x430"); win.transient(parent); win.grab_set()
    txt = scrolledtext.ScrolledText(win, wrap="word", font=LargeFont)
    txt.pack(fill="both", expand=True, padx=10, pady=(10))
    txt.insert("1.0", content); txt.configure(state="disabled")

class LiveTerm:
    """实时终端窗口：滚动显示输出；Ctrl+C/关闭结束；结束后回调 OnFinish(rc, out)"""
    def __init__(self, root: Tk.Tk, cmd: str, title: str, on_finish):
        self.Root, self.Cmd, self.OnFinish = root, cmd, on_finish
        self.Buf = []
        self.Win = Tk.Toplevel(root); self.Win.title(title); self.Win.geometry("820x560"); self.Win.transient(root)
        self.Txt = scrolledtext.ScrolledText(self.Win, wrap="word")
        self.Txt.pack(fill="both", expand=True, padx=10, pady=(10,0))
        bar = Tk.Frame(self.Win); bar.pack(fill="x", padx=10, pady=8)
        Tk.Button(bar, text="停止（Ctrl+C）", command=self.Stop).pack(side="left")
        Tk.Button(bar, text="复制全部", command=self.CopyAll).pack(side="left", padx=(8,0))
        self.Win.bind("<Control-c>", lambda e: self.Stop())
        self.Win.protocol("WM_DELETE_WINDOW", self.Stop)
        self.Proc = SilentPopen(self.Cmd, new_group=True)
        threading.Thread(target=self.ReadLoop, daemon=True).start()
        threading.Thread(target=self.WaitLoop, daemon=True).start()

    def Append(self, s: str): self.Buf.append(s); self.Txt.insert("end", s); self.Txt.see("end")
    def ReadLoop(self):
        try:
            for line in self.Proc.stdout:
                self.Root.after(0, self.Append, line)
        except Exception as e:
            self.Root.after(0, self.Append, f"\n[读取输出异常] {e}\n")
    def WaitLoop(self):
        rc = self.Proc.wait(); out = "".join(self.Buf)
        def Done():
            try: self.Win.destroy()
            except Exception: pass
            self.OnFinish(rc, out)
        self.Root.after(0, Done)
    def Stop(self):
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

        # 变量
        self.PostVar   = Tk.StringVar(root)
        self.DraftVar  = Tk.StringVar(root)
        self.PageVar   = Tk.StringVar(root)
        self.GenVar    = Tk.BooleanVar(root, False)
        self.DeployVar = Tk.BooleanVar(root, False)
        self.ServerVar = Tk.BooleanVar(root, False)
        self.CleanVar  = Tk.BooleanVar(root, False)
        self.TailVar   = Tk.StringVar(root)

        self.BuildUi()

        # 运行预览和上传仓库互斥（双向置灰）
        self._MutualLock = False
        self.ServerVar.trace_add("write", self.OnServerChange)
        self.DeployVar.trace_add("write", self.OnDeployChange)

    # ---------- 组合命令区 ----------
    def PlaceRightCheck(self, text: str, var: Tk.BooleanVar, lx: int, bx: int, y: int):
        lbl = Tk.Label(self.Root, text=text, font=FontMain)
        lbl.place(x=lx, y=y + CkTextYOffset)

        chk = Tk.Checkbutton(self.Root, variable=var, bd=0, highlightthickness=0,
                             padx=0, pady=0, text="", width=0, takefocus=False)
        chk.place(x=bx, y=y + CkBoxYOffset)

        # 点击文字同样勾选
        def toggle(_=None):
            var.set(not var.get())
        lbl.bind("<Button-1>", toggle)

        return lbl, chk

    # ------- UI（place定点） -------
    def BuildUi(self):
        r = self.Root
        # 三行“新建XXX”
        Tk.Label(r, text="新建文章", font=FontMain).place(x=LblX, y=RowY0)
        Tk.Entry(r, textvariable=self.PostVar, font=FontMain, relief="solid", bd=1)\
            .place(x=EntX, y=RowY0 + EntryYOffset, width=EntryWidthPx, height=EntryHeightPx)

        Tk.Label(r, text="新建草稿", font=FontMain).place(x=LblX, y=RowY0+RowStep)
        Tk.Entry(r, textvariable=self.DraftVar, font=FontMain, relief="solid", bd=1)\
            .place(x=EntX, y=RowY0+RowStep + EntryYOffset, width=EntryWidthPx, height=EntryHeightPx)

        Tk.Label(r, text="新建页面", font=FontMain).place(x=LblX, y=RowY0+RowStep*2)
        Tk.Entry(r, textvariable=self.PageVar, font=FontMain, relief="solid", bd=1)\
            .place(x=EntX, y=RowY0+RowStep*2 + EntryYOffset, width=EntryWidthPx, height=EntryHeightPx)

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
        Tk.Entry(r, textvariable=self.TailVar, font=FontMain, relief="solid", bd=1)\
            .place(x=TailEntX, y=TailY + TailYOffset, width=TailEntW, height=TailEntH)
        dot = Tk.Canvas(r, width=InfoBtnSize, height=InfoBtnSize, highlightthickness=0)
        dot.place(x=TailEntX + TailEntW + 4, y=TailY + 3)
        r2 = InfoBtnSize - 2
        dot.create_oval(1,1,r2,r2, outline="#888", fill="#e9e9e9")
        dot.create_text(r2//2, r2//2, text="i", font=("Arial", 10, "bold"))
        dot.bind("<Button-1>", lambda e: self.ShowTailInfo())

        # 底部按钮
        Tk.Button(r, text="安装Hexo", command=self.InstallHexo)\
            .place(x=BtnLeftX,  y=BtnY, width=BtnW, height=BtnH)
        Tk.Button(r, text="运行", command=self.RunAll)\
            .place(x=BtnRightX, y=BtnY, width=BtnW, height=BtnH)

    # ------- 互斥切换（文字勾选框置灰） -------
    def _set_enabled(self, chk: Tk.Checkbutton, lbl: Tk.Label, enabled: bool):
        chk.configure(state="normal" if enabled else "disabled")
        lbl.configure(fg="black" if enabled else "#9e9e9e")

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
            "--force     忽略缓存生成\n"
            "--bail      异常即中止\n\n"
            "Deploy (部署)\n"
            "--generate  部署前先生成\n\n"
            "Server (服务器)\n"
            "--port      指定端口\n"
            "--host      指定 IP\n"
            "--static    禁用监听\n"
            "--log       启用日志"
        )
        PopupText(self.Root, "尾部参数大全", info)

    def AppendTail(self, cmd: str) -> str:
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

    # ------- 运行命令 -------
    def RunAll(self):
        new_seq   = self.BuildNewSeq()
        combo_seq = self.BuildComboSeq()
        if not new_seq and not combo_seq:
            messagebox.showwarning("提示", "请先输入要新建的名称或勾选组合操作。", parent=self.Root)
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
                        self.Root.after(0, lambda: PopupText(self.Root, "错误", out))
                        return
                def OnFinish(rc, out):
                    PopupText(self.Root, "完成" if rc == 0 else "错误", out)
                LiveTerm(self.Root, server_cmd, "预览终端（hexo server）", OnFinish)
            threading.Thread(target=RunHeadThenServer, daemon=True).start()
            return

        if len(full) == 1:
            cmd = self.AppendTail(full[0])
        else:
            last = self.AppendTail(full[-1])
            cmd = " && ".join(full[:-1] + [last])

        def Task():
            code, out = RunShell(cmd)
            self.Root.after(0, lambda: PopupText(self.Root, "完成" if code == 0 else "错误", out))
        threading.Thread(target=Task, daemon=True).start()

    def InstallHexo(self):
        chain = "npm install hexo-cli -g && hexo init blog && cd blog && npm install"
        def OnFinish(rc, out):
            PopupText(self.Root, "完成" if rc == 0 else "错误", out)
        LiveTerm(self.Root, chain, "安装 Hexo（实时输出）", OnFinish)

# 入口
def Main():
    root = Tk.Tk()
    app  = HexoDashApp(root)
    root.mainloop()

if __name__ == "__main__":
    Main()