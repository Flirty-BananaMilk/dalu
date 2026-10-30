"""배포판 만들기: 설치 파일(Setup.exe)과 포터블 zip 을 만든다.

    python installer/build_release.py [--no-setup]

결과(프로젝트의 dist/ 폴더):
    dist/stage/Dalu/   배포 내용물 (runtime/ = 파이썬 런타임 + 필요한 패키지, app/ = 앱, 설치/제거 스크립트)
    dist/Dalu-<버전>-Setup.exe     설치 파일 (모든 Windows 에 있는 C# 컴파일러 csc.exe 로 만든다: 따로 설치할 것이 없다)
    dist/Dalu-<버전>-portable.zip  설치 없이 압축을 풀어 실행하는 버전

- 이 PC 에 설치된 파이썬(3.10)을 통째로 복사해 넣으므로, 쓰는 사람의 PC 에 파이썬이 없어도 된다.
- 개발 PC 의 설정/데이터(%APPDATA%\\Dalu)는 어디에도 들어가지 않는다.
"""
import importlib.metadata as md
import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "dist"
STAGE = OUT / "stage" / "Dalu"
APP_EXT = {".py", ".js", ".html", ".css"}
SKIP_LIB = {"site-packages", "test", "tests", "idlelib", "tkinter", "turtledemo", "lib2to3", "ensurepip", "venv", "pydoc_data", "distutils"}
SKIP_DLL = ("_tkinter", "tcl86", "tk86", "_test", "_msi")


def norm(n):
    return re.sub(r"[-_.]+", "-", n).lower()


def version():
    """배포 버전의 유일한 출처는 dalu.py 의 APP_VERSION (MAJOR.MINOR.PATCH). 형식과 CHANGELOG.md 항목을 확인한다."""
    m = re.search(r'^APP_VERSION\s*=\s*"([^"]+)"', (ROOT / "dalu.py").read_text(encoding="utf-8"), re.M)
    if not m or not re.fullmatch(r"\d+\.\d+\.\d+", m.group(1)):
        sys.exit(f"APP_VERSION 은 MAJOR.MINOR.PATCH 형식이어야 해요 (예: 1.2.0): {m.group(1) if m else '없음'}")
    ver = m.group(1)
    log = ROOT / "CHANGELOG.md"
    if not log.exists() or not re.search(r"^##\s*\[?" + re.escape(ver) + r"\]?(\s|$)", log.read_text(encoding="utf-8"), re.M):
        sys.exit(f"CHANGELOG.md 에 '## {ver}' 항목이 없어요. 이번 버전에서 바뀐 점을 먼저 적어 주세요.")
    return ver


def clean_copy_tree(src, dst, skip_dirs=(), skip_file=lambda n: False):
    for dirpath, dirnames, filenames in os.walk(src):
        rel = Path(dirpath).relative_to(src)
        dirnames[:] = [d for d in dirnames if d != "__pycache__" and not (rel == Path(".") and d in skip_dirs)]
        (dst / rel).mkdir(parents=True, exist_ok=True)
        for f in filenames:
            if f.endswith((".pyc", ".pyo")) or skip_file(f):
                continue
            shutil.copy2(Path(dirpath) / f, dst / rel / f)


def dependency_dists():
    """requirements.txt 의 패키지와 그 의존 패키지(이 PC 에 설치된 것만. macOS/리눅스용 선택 의존은 자연히 빠진다)."""
    need = []
    for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            need.append(norm(line))
    seen, q = {}, list(need)
    while q:
        n = q.pop()
        if n in seen:
            continue
        try:
            d = md.distribution(n)
        except md.PackageNotFoundError:
            seen[n] = None
            continue
        seen[n] = d
        for r in d.requires or []:
            if "extra ==" in r:
                continue
            q.append(norm(re.split(r"[ ;<>=!~\[(]", r.strip())[0]))
    missing_required = [n for n in need if seen.get(n) is None]
    if missing_required:
        sys.exit(f"필요한 패키지가 이 PC 에 없어요: {missing_required}")
    return {n: d for n, d in seen.items() if d is not None}


def make_icon(path):
    """앱 아이콘은 appicon.py 가 그린다(트레이 아이콘과 같은 그림)."""
    sys.path.insert(0, str(ROOT))
    import appicon
    appicon.save_ico(str(path))


def strip_dev_debug(sp):
    """개발 PC 의 pywebview 에 진단용으로 남아 있는 디버그 기록 코드(내 PC 경로가 들어 있다)를 배포본에서만 뺀다."""
    f = sp / "webview" / "platforms" / "winforms.py"
    if not f.exists():
        return
    raw = f.read_bytes().decode("utf-8")
    crlf = "\r\n" in raw
    lines = raw.replace("\r\n", "\n").split("\n")
    out, i, removed = [], 0, False
    while i < len(lines):
        # try: / with open(... wf_debug.log ...) / f.write(...) / except ...: / pass  (5줄)
        if (i + 4 < len(lines) and lines[i].strip() == "try:" and "wf_debug.log" in lines[i + 1]
                and lines[i + 3].strip().startswith("except") and lines[i + 4].strip() == "pass"):
            i += 5
            if i < len(lines) and not lines[i].strip():
                i += 1
            removed = True
            continue
        out.append(lines[i])
        i += 1
    if removed:
        text = "\n".join(out)
        f.write_bytes((text.replace("\n", "\r\n") if crlf else text).encode("utf-8"))
        print("  배포본에서 pywebview 의 개발용 디버그 기록 코드를 뺐습니다")


BINARY_EXT = (".dll", ".pyd", ".exe", ".png", ".gif", ".ico", ".jpg", ".zip", ".pak", ".dat", ".lib", ".so", ".mo", ".whl")


def assert_no_private(stage):
    """배포본(app + runtime 전체)에 이 PC 의 사용자 이름·경로, 옛 이름이 섞여 들어갔는지 검사한다. 있으면 빌드를 멈춘다."""
    import getpass
    bs = chr(92)
    home = str(Path.home())
    user = getpass.getuser()
    needles = [home, home.replace(bs, "/"), bs + "Users" + bs + user + bs, "/Users/" + user + "/"]
    needles = [n.lower().encode() for n in needles if len(n) > 8]
    wb = (bs + "b").encode()
    old_names = [re.compile(wb + b"nusa" + wb)] + [re.compile(re.escape(x)) for x in (b"cider-dynamic-island", b"cider_dynamic_island", b"dynamic island", b"dynamic_island")]
    bad = []
    for q in stage.rglob("*"):
        if not q.is_file() or q.suffix.lower() in BINARY_EXT or "tzdata" in q.parts:      # tzdata: 인도네시아 지명 "Nusa Tenggara" 가 들어 있다(우리 옛 이름이 아니다)
            continue
        try:
            data = q.read_bytes().lower()
        except OSError:
            continue
        hit = next((n.decode("latin1") for n in needles if n in data), None) or next((r.pattern.decode("latin1") for r in old_names if r.search(data)), None)
        if hit:
            bad.append((str(q.relative_to(stage)), hit))
    if bad:
        raise RuntimeError("배포본에 개인 경로/옛 이름이 섞여 있습니다:" + chr(10) + chr(10).join("  %s  (%s)" % (a, b) for a, b in bad[:30]))
    print("  개인 경로·옛 이름 검사: 통과 (app + runtime 전체 텍스트 파일)")


def build_stage():
    if STAGE.parent.exists():
        shutil.rmtree(STAGE.parent)
    STAGE.mkdir(parents=True)
    base = Path(sys.base_prefix)
    rt = STAGE / "runtime"
    rt.mkdir()
    # --- 파이썬 런타임
    for f in ("python.exe", "pythonw.exe", "python310.dll", "python3.dll", "vcruntime140.dll", "vcruntime140_1.dll", "LICENSE.txt"):
        if (base / f).exists():
            shutil.copy2(base / f, rt / f)
    clean_copy_tree(base / "DLLs", rt / "DLLs", skip_file=lambda n: n.lower().startswith(SKIP_DLL) or n.lower().endswith((".ico", ".cat")))
    clean_copy_tree(base / "Lib", rt / "Lib", skip_dirs=SKIP_LIB)
    # --- 필요한 패키지만 site-packages 로
    sp = rt / "Lib" / "site-packages"
    sp.mkdir(parents=True, exist_ok=True)
    dists = dependency_dists()
    for n, d in sorted(dists.items()):
        for f in d.files or []:
            src = Path(d.locate_file(f))
            if "__pycache__" in f.parts or f.suffix in (".pyc", ".pyo") or not src.is_file():
                continue
            if f.parts and f.parts[0] in ("..", "Scripts") or str(f).startswith(".."):      # 콘솔 스크립트 등은 필요 없다
                continue
            dst = sp / f
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    strip_dev_debug(sp)
    # --- 앱
    app = STAGE / "app"
    app.mkdir()
    for p in ROOT.iterdir():
        if p.is_file() and p.suffix in APP_EXT:
            shutil.copy2(p, app / p.name)
    clean_copy_tree(ROOT / "plugin_examples", app / "plugin_examples")
    for doc in ("README.md", "CHANGELOG.md", "LICENSE", "TRADEMARK.md", "SECURITY.md", "PRIVACY.md", "requirements.txt"):
        shutil.copy2(ROOT / doc, app / doc)
    # --- 설치/제거 스크립트, 아이콘, 안내
    for f in ("install.ps1", "uninstall.ps1"):
        shutil.copy2(ROOT / "installer" / f, STAGE / f)
    make_icon(STAGE / "dalu.ico")
    (STAGE / "VERSION.txt").write_text(version(), encoding="utf-8")
    longest = max(len(str(q.relative_to(STAGE))) for q in STAGE.rglob("*") if q.is_file())
    (STAGE / "PATHLEN.txt").write_text(str(longest), encoding="utf-8")        # 설치 위치 + 이 길이가 윈도우 경로 제한(260자)을 넘으면 DLL 을 못 읽는다
    shutil.copy2(ROOT / "installer" / "INSTALL.md", STAGE / "INSTALL.md")
    (STAGE / "Run.cmd").write_text('@echo off\r\nstart "" "%~dp0runtime\\pythonw.exe" "%~dp0app\\dalu.py"\r\n', encoding="ascii")
    write_notices(STAGE / "THIRD_PARTY_NOTICES.txt", dists, base)
    assert_no_private(STAGE)
    return dists


def write_notices(path, dists, base):
    lines = ["Dalu - 포함된 제3자 소프트웨어 / Third-party software included\n", "=" * 78 + "\n\n"]
    lines += ["Dalu 는 비공식 프로젝트이며 Apple, Cider, Spotify, Samsung, Discord, Microsoft 와 제휴 관계가 없습니다. 상표는 각 소유자의 것입니다.\n",
              "Dalu is an unofficial project, not affiliated with Apple, Cider, Spotify, Samsung, Discord or Microsoft. Trademarks belong to their owners.\n",
              "Samsung Galaxy Buds 제어: 패킷 구조는 공개 프로젝트 GalaxyBudsClient(GPL-3.0)를 참고해 직접 구현했고, 그 코드를 포함하지 않습니다 / The Buds protocol was re-implemented from public documentation of GalaxyBudsClient (GPL-3.0); none of its code is included.\n\n"]
    py_lic = base / "LICENSE.txt"
    lines += ["Python 3.10 (Python Software Foundation License)\n", "-" * 78 + "\n", py_lic.read_text(encoding="utf-8", errors="ignore") if py_lic.exists() else "", "\n\n"]
    for n, d in sorted(dists.items()):
        lines += [f"{d.metadata.get('Name', n)} {d.version}  ({(d.metadata.get('License') or d.metadata.get('License-Expression') or '').splitlines()[0][:60] if (d.metadata.get('License') or d.metadata.get('License-Expression')) else 'see below'})\n", "-" * 78 + "\n"]
        found = False
        for f in d.files or []:
            if re.search(r"(^|/|\\)(LICEN[SC]E|COPYING|NOTICE)[^/\\]*$", str(f), re.I):
                try:
                    lines.append(Path(d.locate_file(f)).read_text(encoding="utf-8", errors="ignore") + "\n")
                    found = True
                except Exception:
                    pass
        if not found:
            lines.append("(라이선스 파일이 패키지에 없어요 / no license file shipped with the package)\n")
        lines.append("\n")
    path.write_text("".join(lines), encoding="utf-8")


def make_portable(ver):
    zpath = OUT / f"Dalu-{ver}-portable.zip"
    if zpath.exists():
        zpath.unlink()
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for p in sorted(STAGE.rglob("*")):
            if p.is_file():
                z.write(p, Path("Dalu") / p.relative_to(STAGE))
    return zpath


CSC = os.path.join(os.environ.get("WINDIR", "C:/Windows"), "Microsoft.NET", "Framework64", "v4.0.30319", "csc.exe")


def make_setup(ver, portable_zip):
    """Setup.exe: 모든 Windows 에 들어 있는 C# 컴파일러(csc.exe)로 작은 설치 프로그램을 만들고, 내용물 zip 을 리소스로 넣는다.
    (Windows 기본 도구 IExpress 는 이 환경에서 멈추는 문제가 있어서, 인자 전달과 진행 표시가 되는 직접 만든 껍데기를 쓴다.)"""
    if not os.path.exists(CSC):
        sys.exit("csc.exe 를 찾지 못했어요 (.NET Framework 4 가 필요해요).")
    work = OUT / "setup_build"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    src = (ROOT / "installer" / "SetupStub.cs").read_text(encoding="utf-8").replace("@VERSION@", ver)
    (work / "SetupStub.cs").write_text(src, encoding="utf-8-sig")
    shutil.copy2(portable_zip, work / "payload.zip")
    shutil.copy2(STAGE / "dalu.ico", work / "dalu.ico")
    target = OUT / f"Dalu-{ver}-Setup.exe"
    if target.exists():
        target.unlink()
    cmd = [CSC, "/nologo", "/target:winexe", f"/out:{target}", f"/win32icon:{work / 'dalu.ico'}", f"/resource:{work / 'payload.zip'},payload.zip",
           "/reference:System.IO.Compression.FileSystem.dll", "/reference:System.IO.Compression.dll", "/reference:System.Windows.Forms.dll", "/reference:System.Drawing.dll", str(work / "SetupStub.cs")]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if not target.exists():
        sys.exit(f"Setup.exe 를 만들지 못했어요: {r.stdout} {r.stderr}")
    shutil.rmtree(work, ignore_errors=True)
    return target


def write_checksums(ver, files):
    """배포 파일의 SHA-256 을 dist/Dalu-<버전>-SHA256.txt 에 적는다(내려받은 파일이 맞는지 확인용)."""
    import hashlib
    lines = []
    for f in files:
        h = hashlib.sha256(Path(f).read_bytes()).hexdigest()
        lines.append(f"{h}  {Path(f).name}")
    out = OUT / f"Dalu-{ver}-SHA256.txt"
    out.write_text("\n".join(lines) + "\n", encoding="ascii")
    return out


def main():
    ver = version()
    OUT.mkdir(exist_ok=True)
    print(f"버전 {ver}: 내용물 만드는 중...")
    dists = build_stage()
    size = sum(p.stat().st_size for p in STAGE.rglob("*") if p.is_file())
    print(f"  패키지 {len(dists)}개, 내용물 {size / 1e6:.0f} MB")
    z = make_portable(ver)
    print(f"  포터블 zip: {z.name} ({z.stat().st_size / 1e6:.0f} MB)")
    if "--no-setup" not in sys.argv:
        s = make_setup(ver, z)
        print(f"  설치 파일: {s.name} ({s.stat().st_size / 1e6:.0f} MB)")
        c = write_checksums(ver, [s, z])
        print(f"  체크섬: {c.name}")


if __name__ == "__main__":
    main()
