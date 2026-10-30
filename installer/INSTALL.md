# Dalu(달루) 설치 안내 / Installation

## 한국어

### 설치 (권장)
1. `Dalu-<버전>-Setup.exe` 를 실행합니다.
   - Windows 가 “알 수 없는 게시자” 경고를 띄우면 **추가 정보 › 실행**을 누르세요. (이 설치 파일은 코드 서명이 없어서 나오는 경고예요.)
2. 시키는 대로 진행하면 끝입니다. 관리자 권한은 필요 없고, 현재 사용자에게만 설치돼요.
3. 설치가 끝나면 화면 **위쪽 가운데**에 노치가 나타납니다. 마우스를 올리면 펼쳐지고, 설정은 트레이 아이콘 › 설정에서 열어요.

설치 위치: `%LOCALAPPDATA%\Programs\Dalu` · 내 설정/데이터: `%APPDATA%\Dalu` (업데이트하거나 다시 설치해도 그대로 남아요).

### 설치 없이 써 보기 (포터블)
`Dalu-<버전>-portable.zip` 의 압축을 풀고 `Run.cmd` 를 실행합니다.

### 업데이트
새 Setup.exe 를 그냥 다시 실행하면 덮어써집니다(설정은 유지).

### 제거
**설정 › 앱 › 설치된 앱 › Dalu › 제거**. 내 데이터도 지울지 물어봅니다.

### 필요한 것
- Windows 10 (버전 2004 이상) 또는 Windows 11. Python 은 필요 없어요(포함돼 있어요).
- Microsoft Edge **WebView2 런타임** — Windows 11 에는 기본으로 있고, 없으면 설치 중에 설치할지 물어봅니다(인터넷 필요).
- 음악 표시는 **Cider**(Apple Music 클라이언트)와 Windows 미디어 컨트롤을 지원하는 앱(Spotify, 브라우저 등)에서 동작해요. Cider 가 없어도 시계, 타이머, 포모도로 등은 그대로 쓸 수 있어요.

### Windows 가 "PC 를 보호했습니다" 라고 막을 때 (SmartScreen)
코드 서명이 없는 새 프로그램은 처음에 이 경고가 뜹니다. **추가 정보 → 실행** 을 누르면 설치돼요. 받은 파일이 올바른지 확인하려면 `Dalu-<버전>-SHA256.txt` 의 값과 비교하세요: PowerShell 에서 `Get-FileHash .\Dalu-<버전>-Setup.exe`.

### 무엇이 설치되나요? (보안)
- 파이썬 런타임과 앱 파일만 설치 폴더에 복사됩니다. 인터넷에서 받는 것은 (WebView2 가 없을 때) Microsoft 의 공식 설치 프로그램뿐이에요.
- 가사는 Cider(Apple Music 가사는 Cider 를 거쳐서)와 공개 가사 서비스(NetEase, LRCLIB)에서 찾습니다. 가사는 각 서비스의 것이며 앱은 저장·재배포하지 않아요. 설정에서 끌 수 있어요.
- 클립보드 기록은 기본으로 꺼져 있고, 켜도 메모리에만 있고 저장되지 않아요.

---

## English

### Install (recommended)
1. Run `Dalu-<version>-Setup.exe`.
   - If Windows SmartScreen warns about an unknown publisher, choose **More info › Run anyway** (the installer is not code-signed).
2. Follow the prompts. No administrator rights are needed; it installs for the current user only.
3. The notch appears at the **top centre** of your screen. Hover to expand; open Settings from the tray icon.

Install location: `%LOCALAPPDATA%\Programs\Dalu` · Your settings/data: `%APPDATA%\Dalu` (kept across updates and reinstalls).

### Portable
Unzip `Dalu-<version>-portable.zip` and run `Run.cmd`.

### Update
Just run the newer Setup.exe again; it overwrites the app and keeps your settings.

### Uninstall
**Settings › Apps › Installed apps › Dalu › Uninstall**. You are asked whether to delete your data too.

### If Windows says "Windows protected your PC" (SmartScreen)
New programs without a code-signing certificate get this warning at first. Click **More info → Run anyway**. To verify your download, compare with the value in `Dalu-<version>-SHA256.txt`: in PowerShell run `Get-FileHash .\Dalu-<version>-Setup.exe`.

### Requirements
- Windows 10 (2004 or later) or Windows 11. Python is bundled.
- The Microsoft Edge **WebView2 Runtime** (preinstalled on Windows 11; the installer offers to install it if missing - needs internet).
- Music display works with **Cider** (Apple Music client) and any app that supports Windows media controls (Spotify, browsers, ...). Without Cider you still get the clock, timers, Pomodoro and more.


---

## 简体中文

1. 运行 `Dalu-<版本>-Setup.exe`。若 Windows SmartScreen 提示“已保护你的电脑”（安装程序没有代码签名），请点击 **更多信息 › 仍要运行**。
2. 无需管理员权限，仅为当前用户安装，Python 已内置。刘海会出现在屏幕**顶部中央**，鼠标移上去会展开，设置可从托盘图标打开。
3. 免安装：解压 `Dalu-<版本>-portable.zip` 后运行 `Run.cmd`。更新：直接再运行新的 Setup.exe（设置会保留）。卸载：**设置 › 应用 › 已安装的应用 › Dalu**。
4. 校验下载文件：在 PowerShell 中运行 `Get-FileHash .\Dalu-<版本>-Setup.exe`，并与 `Dalu-<版本>-SHA256.txt` 比对。
5. 需要 Windows 10（2004 及以上）或 Windows 11，以及 Microsoft Edge **WebView2 运行时**（缺少时安装程序会询问是否安装）。音乐显示支持 **Cider** 和任何支持 Windows 媒体控制的应用（Spotify、浏览器等）。设置与数据保存在 `%APPDATA%\Dalu`。
6. 隐私：请见 `PRIVACY.md`（没有账号、没有统计，只有开启相应功能时才会联网）。

## 日本語

1. `Dalu-<バージョン>-Setup.exe` を実行します。Windows SmartScreen が「PC が保護されました」と表示した場合（インストーラーにコード署名がないため）は、**詳細情報 › 実行** を選んでください。
2. 管理者権限は不要で、現在のユーザーにだけインストールされます（Python は同梱）。ノッチは画面の**上部中央**に表示され、マウスを乗せると展開します。設定はトレイアイコンから開けます。
3. インストールせずに使うには、`Dalu-<バージョン>-portable.zip` を展開して `Run.cmd` を実行します。更新は新しい Setup.exe をもう一度実行するだけです（設定は残ります）。アンインストール：**設定 › アプリ › インストールされているアプリ › Dalu**。
4. ダウンロードの確認：PowerShell で `Get-FileHash .\Dalu-<バージョン>-Setup.exe` を実行し、`Dalu-<バージョン>-SHA256.txt` の値と比べてください。
5. Windows 10（2004 以降）または Windows 11 と、Microsoft Edge **WebView2 ランタイム**が必要です（未導入ならインストーラーが確認します）。音楽表示は **Cider** と、Windows のメディアコントロールに対応したアプリ（Spotify、ブラウザーなど）で動作します。設定とデータは `%APPDATA%\Dalu` に保存されます。
6. プライバシー：`PRIVACY.md` をご覧ください（アカウントも統計収集もなく、その機能を使うときだけ通信します）。
