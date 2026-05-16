import ctypes
from ui.main_window import MainWindow

if __name__ == "__main__":
    # 尝试开启 Windows 高 DPI 感知，消除界面模糊
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except:
            pass

    app = MainWindow()
    app.mainloop()
