# Dalu 설치 스크립트 / Installer
# - 설치 위치: 기본 %LOCALAPPDATA%\Programs\Dalu (관리자 권한 필요 없음, 현재 사용자 전용)
# - 설정/가사 캐시 같은 사용자 데이터는 %APPDATA%\Dalu 에 따로 있어서 업데이트·재설치해도 그대로 남는다.
# - 아래 매개변수 중 -StartMenuDir / -RegistryRoot / -RunKey 는 시험용이다(실제 시작 메뉴·레지스트리를 건드리지 않고 확인할 때).
param(
    [string]$InstallDir = (Join-Path $env:LOCALAPPDATA 'Programs\Dalu'),
    [string]$StartMenuDir = (Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs'),
    [string]$RegistryRoot = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall',
    [string]$RunKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run',
    [switch]$Autostart,        # Windows 시작 시 자동 실행 (대화형에서는 묻는다)
    [switch]$NoLaunch,         # 설치 후 바로 실행하지 않는다
    [switch]$Quiet,            # 대화상자 없이 설치 (자동 실행은 -Autostart 로만 켠다)
    [switch]$NoWebView2Check   # WebView2 런타임 확인/설치를 건너뛴다
)
$ErrorActionPreference = 'Stop'
$Src = $PSScriptRoot
$AppName = 'Dalu'
$UninstallId = 'Dalu'
$RunName = 'Dalu'          # 앱(prefs.py)의 '시작 프로그램' 설정이 쓰는 이름과 같아야 한다
$uiLang = (Get-UICulture).TwoLetterISOLanguageName      # ko | zh | ja | 그 밖은 영어
function T($k, $e, $z, $j) { switch ($uiLang) { 'ko' { $k } 'zh' { if ($z) { $z } else { $e } } 'ja' { if ($j) { $j } else { $e } } default { $e } } }
$Log = Join-Path $env:TEMP 'Dalu-install.log'
function Log($m) { try { Add-Content -Path $Log -Value ("[{0}] {1}" -f (Get-Date -Format 'HH:mm:ss'), $m) -Encoding UTF8 } catch {} }
Add-Type -AssemblyName PresentationFramework
function Say($text, $title, $buttons = 'OK', $icon = 'Information') {
    if ($Quiet) { return 'Yes' }
    return [System.Windows.MessageBox]::Show($text, $title, $buttons, $icon).ToString()
}
Log "install start: $InstallDir"

try {
    # --- 사전 확인: 페이로드가 온전한가
    foreach ($need in 'runtime\pythonw.exe', 'app\dalu.py') {
        if (-not (Test-Path (Join-Path $Src $need))) { throw (T "설치 파일이 온전하지 않아요: $need 가 없습니다." "The installer files are incomplete: $need is missing." "安装文件不完整：缺少 $need。" "インストールファイルが不完全です：$need がありません。") }
    }
    $maxRel = 0
    if (Test-Path (Join-Path $Src 'PATHLEN.txt')) { [void][int]::TryParse((Get-Content (Join-Path $Src 'PATHLEN.txt') -Raw).Trim(), [ref]$maxRel) }
    if (($InstallDir.TrimEnd('').Length + 1 + $maxRel) -gt 250) { throw (T "설치 위치가 너무 길어요. Windows 의 경로 길이 제한(260자) 때문에 더 짧은 폴더를 골라 주세요. (이 위치의 가장 긴 파일 경로: $($InstallDir.TrimEnd('').Length + 1 + $maxRel)자)" "The install location is too long for Windows' 260-character path limit. Please choose a shorter folder. (longest file path here: $($InstallDir.TrimEnd('').Length + 1 + $maxRel) characters)" "安装位置太长，超出了 Windows 的 260 个字符路径限制。请选择更短的文件夹。（此位置最长的文件路径：$($InstallDir.TrimEnd('').Length + 1 + $maxRel) 个字符）" "インストール先が長すぎて、Windows の 260 文字のパス長制限を超えます。もっと短いフォルダーを選んでください。（この場所で最も長いファイルのパス：$($InstallDir.TrimEnd('').Length + 1 + $maxRel) 文字）") }
    if ([Environment]::OSVersion.Version.Major -lt 10) { throw (T 'Windows 10 이상이 필요해요.' 'Windows 10 or later is required.' '需要 Windows 10 或更高版本。' 'Windows 10 以降が必要です。') }

    # --- 업데이트인지 확인: 설치된 버전이 이 설치 파일보다 새것이면 낮추기 전에 묻는다
    $newVer = if (Test-Path (Join-Path $Src 'VERSION.txt')) { (Get-Content (Join-Path $Src 'VERSION.txt') -Raw).Trim() } else { '0' }
    $oldFile = Join-Path $InstallDir 'VERSION.txt'
    if (Test-Path $oldFile) {
        $oldVer = (Get-Content $oldFile -Raw).Trim()
        Log "installed $oldVer, installing $newVer"
        $o = $null; $n = $null
        if ([version]::TryParse($oldVer, [ref]$o) -and [version]::TryParse($newVer, [ref]$n) -and $o -gt $n) {
            $ans = Say (T "이미 더 새 버전($oldVer)이 설치되어 있어요. 이전 버전($newVer)으로 바꿀까요?" "A newer version ($oldVer) is already installed. Replace it with the older $newVer?" "已经安装了更新的版本 ($oldVer)。要换成较旧的 $newVer 吗？" "新しいバージョン ($oldVer) がすでにインストールされています。古い $newVer に置き換えますか？") $AppName 'YesNo' 'Question'
            if ($ans -ne 'Yes') { Log 'downgrade declined'; exit 0 }
        }
    }

    # --- 이미 설치된 것이 실행 중이면 끈다 (설치 폴더 안의 프로세스만: 다른 곳에서 개발 중인 것은 건드리지 않는다)
    $prefix = ($InstallDir.TrimEnd('\') + '\').ToLowerInvariant()
    Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.ExecutablePath -and $_.ExecutablePath.ToLowerInvariant().StartsWith($prefix) } | ForEach-Object {
        Log "stopping pid $($_.ProcessId)"; Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Milliseconds 700

    # --- 파일 복사 (robocopy /MIR: 업데이트 때 옛 파일이 남지 않는다. 사용자 데이터는 이 폴더 밖에 있다)
    New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
    foreach ($d in 'runtime', 'app') {
        $null = & robocopy (Join-Path $Src $d) (Join-Path $InstallDir $d) /MIR /NFL /NDL /NJH /NJS /NP /R:2 /W:1
        if ($LASTEXITCODE -ge 8) { throw (T "파일을 복사하지 못했어요 ($d, 오류 $LASTEXITCODE)." "Could not copy files ($d, error $LASTEXITCODE)." "无法复制文件 ($d，错误 $LASTEXITCODE)。" "ファイルをコピーできませんでした ($d、エラー $LASTEXITCODE)。") }
    }
    foreach ($f in 'uninstall.ps1', 'dalu.ico', 'THIRD_PARTY_NOTICES.txt', 'VERSION.txt') {
        if (Test-Path (Join-Path $Src $f)) { Copy-Item (Join-Path $Src $f) (Join-Path $InstallDir $f) -Force }
    }
    $Pyw = Join-Path $InstallDir 'runtime\pythonw.exe'
    $Script = Join-Path $InstallDir 'app\dalu.py'
    $Ico = Join-Path $InstallDir 'dalu.ico'
    $Version = if (Test-Path (Join-Path $Src 'VERSION.txt')) { (Get-Content (Join-Path $Src 'VERSION.txt') -Raw).Trim() } else { '1.0' }

    # --- 시작 메뉴 바로가기
    New-Item -ItemType Directory -Force -Path $StartMenuDir | Out-Null
    $Lnk = Join-Path $StartMenuDir "$AppName.lnk"
    $sh = New-Object -ComObject WScript.Shell
    $s = $sh.CreateShortcut($Lnk)
    $s.TargetPath = $Pyw
    $s.Arguments = '"' + $Script + '"'
    $s.WorkingDirectory = Join-Path $InstallDir 'app'
    $s.IconLocation = $Ico
    $s.Description = 'Dalu'
    $s.Save()

    # --- '설정 > 앱'(제거 프로그램)에 등록
    $key = Join-Path $RegistryRoot $UninstallId
    New-Item -Path $key -Force | Out-Null
    $size = [int]((Get-ChildItem $InstallDir -Recurse -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum / 1KB)
    $uninst = 'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "' + (Join-Path $InstallDir 'uninstall.ps1') + '"'
    if ($StartMenuDir -ne (Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs')) { $uninst += ' -StartMenuDir "' + $StartMenuDir + '"' }
    if ($RegistryRoot -ne 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall') { $uninst += ' -RegistryRoot "' + $RegistryRoot + '" -RunKey "' + $RunKey + '"' }
    $props = @{ DisplayName = $AppName; DisplayVersion = $Version; Publisher = 'Dalu'; InstallLocation = $InstallDir; DisplayIcon = $Ico
                UninstallString = $uninst; EstimatedSize = $size; InstallDate = (Get-Date -Format 'yyyyMMdd') }
    foreach ($k in $props.Keys) { New-ItemProperty -Path $key -Name $k -Value $props[$k] -Force | Out-Null }
    New-ItemProperty -Path $key -Name NoModify -Value 1 -PropertyType DWord -Force | Out-Null
    New-ItemProperty -Path $key -Name NoRepair -Value 1 -PropertyType DWord -Force | Out-Null

    # --- WebView2 런타임 (Windows 11 에는 기본으로 들어 있고, Windows 10 에는 없을 수 있다)
    if (-not $NoWebView2Check) {
        $guid = '{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}'
        $found = $false
        foreach ($p in "HKLM:\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\$guid", "HKLM:\SOFTWARE\Microsoft\EdgeUpdate\Clients\$guid", "HKCU:\Software\Microsoft\EdgeUpdate\Clients\$guid") {
            try { $v = (Get-ItemProperty -Path $p -ErrorAction Stop).pv; if ($v -and $v -ne '0.0.0.0') { $found = $true } } catch {}
        }
        Log "webview2 found=$found"
        if (-not $found) {
            $ans = Say (T 'Microsoft Edge WebView2 런타임이 필요해요. 지금 Microsoft 에서 내려받아 설치할까요? (약 2분, 인터넷 연결 필요)' 'The Microsoft Edge WebView2 Runtime is required. Download and install it from Microsoft now? (about 2 minutes, needs internet)' '需要 Microsoft Edge WebView2 运行时。现在从 Microsoft 下载并安装吗？（约 2 分钟，需要联网）' 'Microsoft Edge WebView2 ランタイムが必要です。今すぐ Microsoft からダウンロードしてインストールしますか？（約 2 分、インターネット接続が必要）') $AppName 'YesNo' 'Question'
            if ($ans -eq 'Yes') {
                try {
                    $bs = Join-Path $env:TEMP 'MicrosoftEdgeWebview2Setup.exe'
                    Invoke-WebRequest -Uri 'https://go.microsoft.com/fwlink/p/?LinkId=2124703' -OutFile $bs -UseBasicParsing
                    $null = Start-Process -FilePath $bs -ArgumentList '/silent', '/install' -Wait -PassThru
                } catch { Log "webview2 install failed: $_" ; $null = Say (T 'WebView2 설치에 실패했어요. https://developer.microsoft.com/microsoft-edge/webview2 에서 직접 설치해 주세요.' 'Could not install WebView2. Please install it from https://developer.microsoft.com/microsoft-edge/webview2' '无法安装 WebView2。请从 https://developer.microsoft.com/microsoft-edge/webview2 手动安装。' 'WebView2 をインストールできませんでした。https://developer.microsoft.com/microsoft-edge/webview2 から手動でインストールしてください。') $AppName 'OK' 'Warning' }
            }
        }
    }

    # --- Windows 시작 시 자동 실행
    $auto = [bool]$Autostart
    if (-not $Quiet -and -not $Autostart) { $auto = ((Say (T 'Windows 를 시작할 때 노치를 자동으로 실행할까요? (설정에서 언제든 바꿀 수 있어요)' 'Start the notch automatically when Windows starts? (You can change this in Settings any time.)' 'Windows 启动时自动运行灵动岛吗？（之后可随时在设置中更改）' 'Windows の起動時にノッチを自動で開始しますか？（設定でいつでも変更できます）') $AppName 'YesNo' 'Question') -eq 'Yes') }
    if ($auto) {
        New-Item -Path $RunKey -Force | Out-Null
        New-ItemProperty -Path $RunKey -Name $RunName -Value ('"' + $Pyw + '" "' + $Script + '"') -Force | Out-Null
    }

    # --- 실행
    if (-not $NoLaunch) {
        Start-Process -FilePath $Pyw -ArgumentList ('"' + $Script + '"') -WorkingDirectory (Join-Path $InstallDir 'app')
    }
    Log 'install ok'
    $null = Say (T "설치가 끝났어요.`n`n노치는 화면 위쪽 가운데에 나타나요. 마우스를 올리면 펼쳐지고, 설정은 트레이 아이콘에서 열 수 있어요.`n(제거: 설정 › 앱 › $AppName)" "Installation finished.`n`nThe notch appears at the top centre of your screen. Hover it to expand; open Settings from the tray icon.`n(Uninstall: Settings > Apps > $AppName)" "安装完成。`n`n灵动岛会出现在屏幕顶部中央。鼠标移上去会展开，设置可从托盘图标打开。`n（卸载：设置 › 应用 › $AppName）" "インストールが完了しました。`n`nノッチは画面の上部中央に表示されます。マウスを乗せると展開し、設定はトレイアイコンから開けます。`n（アンインストール：設定 › アプリ › $AppName）") $AppName
}
catch {
    Log "install FAILED: $_"
    $null = Say ((T '설치하지 못했어요: ' 'Installation failed: ' '安装失败：' 'インストールに失敗しました：') + $_.Exception.Message + "`n`n" + (T "자세한 내용: $Log" "Details: $Log" "详细信息：$Log" "詳細：$Log")) $AppName 'OK' 'Error'
    exit 1
}
