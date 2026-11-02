# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Flirty_BananaMilk — 상업적 이용 금지, 자세한 내용은 LICENSE
"""게임 감지: 앞에 있는 전체화면 앱이 '게임'(DirectX / OpenGL / Vulkan 으로 그리는 앱)인지 판단한다.

유튜브·영상 플레이어·브라우저처럼 그래픽 DLL 을 쓰는 일반 전체화면 앱은 게임으로 치지 않도록,
  1) 앞의 창이 모니터 전체를 덮고(sysmon.fullscreen_foreground_hwnd),
  2) 그 프로세스가 DirectX 9/10/11/12 · OpenGL · Vulkan DLL 중 하나를 불러왔고,
  3) 크로미움(Electron/CEF/WebView2)·WPF 같은 앱 틀 DLL 이 없고, 실행 파일이 기본 제외 목록(브라우저·영상 플레이어·발표 프로그램 등)이나 사용자의 '절대 숨기지 않음' 목록에 없을 때 게임으로 본다.
윈도우가 'DirectX 전체화면 중'이라고 알려 주는 경우(SHQueryUserNotificationState)도 게임이다.
안티치트 같은 보호 때문에 프로세스의 DLL 목록을 읽지 못하면, 전체화면을 덮고 있다는 사실만으로 게임으로 본다.
사용자의 '항상 숨김' 목록에 있는 실행 파일은 그래픽 DLL 검사 없이 (전체화면이면) 게임으로 본다.

이 모듈은 프로세스의 파일 이름과 불러온 DLL 이름만 읽는다. 화면·창 내용·입력은 읽지 않는다.
"""
import ctypes
import os
from ctypes import wintypes

GRAPHICS_DLLS = frozenset({
    "d3d9.dll", "d3d10.dll", "d3d10_1.dll", "d3d10core.dll", "d3d11.dll", "d3d12.dll",
    "opengl32.dll", "vulkan-1.dll",
})

# 그래픽 DLL 을 쓰지만 게임이 아닌 전체화면 앱 (소문자 실행 파일 이름)
DEFAULT_EXCLUDED = frozenset({
    "chrome.exe", "msedge.exe", "firefox.exe", "brave.exe", "opera.exe", "vivaldi.exe", "iexplore.exe", "arc.exe", "whale.exe",
    "vlc.exe", "potplayer.exe", "potplayermini.exe", "potplayermini64.exe", "potplayer64.exe", "mpc-hc.exe", "mpc-hc64.exe", "mpc-be.exe", "mpc-be64.exe",
    "mpv.exe", "wmplayer.exe", "kmplayer.exe", "gom.exe", "gomplayer.exe", "video.ui.exe", "microsoft.media.player.exe", "movies.exe",
    "spotify.exe", "applemusic.exe", "itunes.exe", "cider.exe", "netflix.exe",
    "explorer.exe", "searchhost.exe", "startmenuexperiencehost.exe", "shellexperiencehost.exe", "lockapp.exe",
    "powerpnt.exe", "winword.exe", "excel.exe", "acrord32.exe", "acrobat.exe", "soffice.bin", "sumatrapdf.exe",
    "teams.exe", "ms-teams.exe", "zoom.exe", "slack.exe", "discord.exe", "obs64.exe", "obs32.exe",
    "mstsc.exe", "vmware.exe", "vmware-vmx.exe", "virtualboxvm.exe", "teamviewer.exe", "anydesk.exe", "parsecd.exe",
    "dalu.exe",
})

# 게임이 아니라 '앱 틀'이라는 표시가 되는 DLL: 크로미움 계열(Electron/CEF/WebView2 앱은 ANGLE 로 그려서 libEGL 을 쓴다), WPF.
# 이런 DLL 이 있으면 그래픽 DLL 이 있어도 게임으로 보지 않는다 (사용자의 '항상 숨김' 목록은 이 검사보다 앞선다).
APP_FRAMEWORK_DLLS = frozenset({
    "libegl.dll", "libglesv2.dll", "chrome_elf.dll", "libcef.dll", "webview2loader.dll",
    "wpfgfx_cor3.dll", "wpfgfx_v0400.dll", "presentationnative_cor3.dll", "presentationnative_v0400.dll",
})
# 프로세스만으로는 어떤 앱인지 알 수 없는 껍데기(UWP 앱 틀): 윈도우가 'DirectX 전체화면'이라고 알려 줄 때만 게임으로 본다
AMBIGUOUS_HOSTS = frozenset({"applicationframehost.exe"})

QUNS_RUNNING_D3D_FULL_SCREEN = 3

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
PROCESS_VM_READ = 0x0010
LIST_MODULES_ALL = 0x03


def parse_names(text):
    """'a.exe, b' -> {'a.exe', 'b.exe'}: 쉼표/줄바꿈으로 나눠 소문자로, 확장자가 없으면 .exe 를 붙인다."""
    out = set()
    for part in str(text or "").replace("\n", ",").replace(";", ",").split(","):
        p = part.strip().strip('"').lower()
        if not p:
            continue
        p = os.path.basename(p.replace("/", "\\").split("\\")[-1])
        if "." not in p:
            p += ".exe"
        out.add(p)
    return out


def decide(exe, modules, d3d_fullscreen=False, always=(), never=(), excluded=DEFAULT_EXCLUDED):
    """순수 판정. exe: 소문자 실행 파일 이름(모르면 ''), modules: 소문자 DLL 이름 모음(못 읽으면 None).
    전체화면 앱이라는 전제에서 '게임이면 True'."""
    exe = (exe or "").lower()
    if exe and exe in never:
        return False
    if exe and exe in always:
        return True
    if exe and exe in AMBIGUOUS_HOSTS:
        return bool(d3d_fullscreen)
    if exe and exe in excluded:
        return False
    if d3d_fullscreen:                    # 윈도우가 직접 'DirectX 전체화면'이라고 알려 줌
        return True
    if modules is None:                   # DLL 목록을 못 읽음(보호된 프로세스): 전체화면이라는 사실로 판단
        return True
    mods = {m.lower() for m in modules}
    if APP_FRAMEWORK_DLLS & mods:         # Electron/CEF/WebView2/WPF 앱: 전체화면(F11 등)이어도 게임이 아니다
        return False
    return bool(GRAPHICS_DLLS & mods)


# ---------------------------------------------------------------------- Windows 호출
def _exe_of(pid):
    """pid 의 실행 파일 이름(소문자). 못 읽으면 ''."""
    k32 = ctypes.windll.kernel32
    k32.OpenProcess.restype = wintypes.HANDLE
    h = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(1024)
        n = wintypes.DWORD(1024)
        if k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n)):
            return os.path.basename(buf.value).lower()
        return ""
    finally:
        k32.CloseHandle(h)


def _modules_of(pid):
    """pid 가 불러온 DLL 이름 집합(소문자). 읽을 수 없으면 None."""
    k32 = ctypes.windll.kernel32
    try:
        psapi = ctypes.windll.psapi
        k32.OpenProcess.restype = wintypes.HANDLE
        h = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_VM_READ, False, pid)
        if not h:
            return None
        try:
            psapi.EnumProcessModulesEx.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.HMODULE), wintypes.DWORD,
                                                   ctypes.POINTER(wintypes.DWORD), wintypes.DWORD]
            psapi.GetModuleBaseNameW.argtypes = [wintypes.HANDLE, wintypes.HMODULE, wintypes.LPWSTR, wintypes.DWORD]
            cap = 1024
            while True:
                arr = (wintypes.HMODULE * cap)()
                need = wintypes.DWORD(0)
                if not psapi.EnumProcessModulesEx(h, arr, ctypes.sizeof(arr), ctypes.byref(need), LIST_MODULES_ALL):
                    return None
                count = need.value // ctypes.sizeof(wintypes.HMODULE)
                if count <= cap:
                    break
                cap = count + 64
            names = set()
            buf = ctypes.create_unicode_buffer(260)
            for i in range(count):
                if psapi.GetModuleBaseNameW(h, arr[i], buf, 260):
                    names.add(buf.value.lower())
            return names
        finally:
            k32.CloseHandle(h)
    except Exception:
        return None


def _d3d_fullscreen_state():
    """SHQueryUserNotificationState == QUNS_RUNNING_D3D_FULL_SCREEN ?"""
    try:
        state = ctypes.c_int(0)
        if ctypes.windll.shell32.SHQueryUserNotificationState(ctypes.byref(state)) == 0:
            return state.value == QUNS_RUNNING_D3D_FULL_SCREEN
    except Exception:
        pass
    return False


def foreground_game(own_hwnd=None, always=(), never=(), fullscreen_hwnd=None):
    """앞의 전체화면 앱이 게임이면 그 실행 파일 이름(없으면 '게임'이라는 뜻의 '?'), 아니면 ''.
    always/never: parse_names 로 만든 소문자 집합."""
    try:
        import sysmon
        hwnd = fullscreen_hwnd if fullscreen_hwnd is not None else sysmon.fullscreen_foreground_hwnd(own_hwnd)
        if not hwnd:
            return ""
        pid = wintypes.DWORD(0)
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if not pid.value:
            return ""
        exe = _exe_of(pid.value)
        if exe and exe in never:
            return ""
        mods = None
        if not (exe and exe in always):
            mods = _modules_of(pid.value)
        return (exe or "?") if decide(exe, mods, _d3d_fullscreen_state(), always, never) else ""
    except Exception:
        return ""
