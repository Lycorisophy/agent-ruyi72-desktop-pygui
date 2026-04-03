#!/usr/bin/env python3
"""窗口管理器"""
import argparse
import json
import subprocess
import sys


def list_windows():
    ps_script = '''
Add-Type @"
using System;
using System.Runtime.InteropServices;
using System.Text;
using System.Collections.Generic;
public class WindowHelper {
    [DllImport("user32.dll")]
    public static extern bool EnumWindows(EnumWindowsProc lpEnumFunc, IntPtr lParam);
    public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);
    [DllImport("user32.dll")]
    public static extern int GetWindowText(IntPtr hWnd, StringBuilder lpString, int nMaxCount);
    [DllImport("user32.dll")]
    public static extern int GetWindowTextLength(IntPtr hWnd);
    [DllImport("user32.dll")]
    public static extern bool IsWindowVisible(IntPtr hWnd);
    public static List<string> GetWindows() {
        List<string> windows = new List<string>();
        EnumWindows((hWnd, lParam) => {
            if (IsWindowVisible(hWnd)) {
                int len = GetWindowTextLength(hWnd);
                if (len > 0) {
                    StringBuilder sb = new StringBuilder(len + 1);
                    GetWindowText(hWnd, sb, sb.Capacity);
                    string title = sb.ToString();
                    if (!string.IsNullOrWhiteSpace(title)) {
                        windows.Add(title);
                    }
                }
            }
            return true;
        }, IntPtr.Zero);
        return windows;
    }
}
"@
$windows = [WindowHelper]::GetWindows()
$windows | ConvertTo-Json
'''
    try:
        result = subprocess.run(["powershell", "-Command", ps_script], capture_output=True, text=True, timeout=10)
        if result.returncode == 0 and result.stdout.strip():
            import json
            return json.loads(result.stdout)
    except:
        pass
    return []


def switch_window(title):
    ps_script = f'''
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class WindowHelper {{
    [DllImport("user32.dll")]
    public static extern bool SetForegroundWindow(IntPtr hWnd);
    [DllImport("user32.dll")]
    public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
    public const int SW_RESTORE = 9;
    public static void ActivateWindow(string title) {{
        IntPtr hWnd = FindWindowByTitle(title);
        if (hWnd != IntPtr.Zero) {{
            ShowWindow(hWnd, SW_RESTORE);
            SetForegroundWindow(hWnd);
        }}
    }}
    [DllImport("user32.dll")]
    public static extern IntPtr FindWindow(string lpClassName, string lpWindowName);
    public static IntPtr FindWindowByTitle(string title) {{
        IntPtr hWnd = FindWindow(null, title);
        if (hWnd != IntPtr.Zero) return hWnd;
        return IntPtr.Zero;
    }}
}}
"@
[WindowHelper]::ActivateWindow("{title}")
Write-Output "ok"
'''
    try:
        result = subprocess.run(["powershell", "-Command", ps_script], capture_output=True, text=True, timeout=5)
        return result.returncode == 0
    except:
        return False


def minimize_window(title):
    ps_script = f'''
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class WindowHelper {{
    [DllImport("user32.dll")]
    public static extern IntPtr FindWindow(string lpClassName, string lpWindowName);
    [DllImport("user32.dll")]
    public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
    public const int SW_MINIMIZE = 6;
    public static void MinimizeWindow(string title) {{
        IntPtr hWnd = FindWindow(null, title);
        if (hWnd != IntPtr.Zero) ShowWindow(hWnd, SW_MINIMIZE);
    }}
}}
"@
[WindowHelper]::MinimizeWindow("{title}")
Write-Output "ok"
'''
    try:
        result = subprocess.run(["powershell", "-Command", ps_script], capture_output=True, text=True, timeout=5)
        return result.returncode == 0
    except:
        return False


def maximize_window(title):
    ps_script = f'''
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class WindowHelper {{
    [DllImport("user32.dll")]
    public static extern IntPtr FindWindow(string lpClassName, string lpWindowName);
    [DllImport("user32.dll")]
    public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
    public const int SW_MAXIMIZE = 3;
    public static void MaximizeWindow(string title) {{
        IntPtr hWnd = FindWindow(null, title);
        if (hWnd != IntPtr.Zero) ShowWindow(hWnd, SW_MAXIMIZE);
    }}
}}
"@
[WindowHelper]::MaximizeWindow("{title}")
Write-Output "ok"
'''
    try:
        result = subprocess.run(["powershell", "-Command", ps_script], capture_output=True, text=True, timeout=5)
        return result.returncode == 0
    except:
        return False


def close_window(title):
    ps_script = f'''
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class WindowHelper {{
    [DllImport("user32.dll")]
    public static extern IntPtr FindWindow(string lpClassName, string lpWindowName);
    [DllImport("user32.dll")]
    public static extern bool PostMessage(IntPtr hWnd, uint Msg, IntPtr wParam, IntPtr lParam);
    public const uint WM_CLOSE = 0x0010;
    public static void CloseWindow(string title) {{
        IntPtr hWnd = FindWindow(null, title);
        if (hWnd != IntPtr.Zero) PostMessage(hWnd, WM_CLOSE, IntPtr.Zero, IntPtr.Zero);
    }}
}}
"@
[WindowHelper]::CloseWindow("{title}")
Write-Output "ok"
'''
    try:
        result = subprocess.run(["powershell", "-Command", ps_script], capture_output=True, text=True, timeout=5)
        return result.returncode == 0
    except:
        return False


def main():
    parser = argparse.ArgumentParser(description="窗口管理器")
    parser.add_argument("--list", action="store_true", help="列出所有窗口")
    parser.add_argument("--switch", help="切换到窗口")
    parser.add_argument("--minimize", help="最小化窗口")
    parser.add_argument("--maximize", help="最大化窗口")
    parser.add_argument("--close", help="关闭窗口")
    parser.add_argument("--json", action="store_true", help="JSON输出")
    args = parser.parse_args()

    if args.list:
        windows = list_windows()
        if args.json:
            print(json.dumps({"windows": windows}, indent=2, ensure_ascii=False))
        else:
            print("===== 窗口列表 =====")
            for i, w in enumerate(windows):
                print(f"{i+1}. {w}")
        return 0

    if args.switch:
        if switch_window(args.switch):
            print(f"✓ 已切换到: {args.switch}")
        else:
            print(f"✗ 未找到窗口: {args.switch}")
        return 0

    if args.minimize:
        if minimize_window(args.minimize):
            print(f"✓ 已最小化: {args.minimize}")
        else:
            print(f"✗ 未找到窗口: {args.minimize}")
        return 0

    if args.maximize:
        if maximize_window(args.maximize):
            print(f"✓ 已最大化: {args.maximize}")
        else:
            print(f"✗ 未找到窗口: {args.maximize}")
        return 0

    if args.close:
        if close_window(args.close):
            print(f"✓ 已关闭: {args.close}")
        else:
            print(f"✗ 未找到窗口: {args.close}")
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
