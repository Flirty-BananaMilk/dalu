# Dalu 제거 스크립트 / Uninstaller
# 기본은 사용자 데이터(%APPDATA%\Dalu: 설정, 할 일, 가사 캐시)를 남긴다. -RemoveData 로 함께 지운다.
param(
    [string]$InstallDir = $PSScriptRoot,
    [string]$StartMenuDir = (Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs'),
    [string]$RegistryRoot = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall',
    [string]$RunKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run',
    [string]$DataDir = (Join-Path $env:APPDATA 'Dalu'),
    [switch]$RemoveData,
    [switch]$Quiet,
    [switch]$FromTemp
)
$ErrorActionPreference = 'Continue'
$AppName = 'Dalu'
$UninstallId = 'Dalu'
$RunName = 'Dalu'
$uiLang = (Get-UICulture).TwoLetterISOLanguageName      # ko | zh | ja | 그 밖은 영어
function T($k, $e, $z, $j) { switch ($uiLang) { 'ko' { $k } 'zh' { if ($z) { $z } else { $e } } 'ja' { if ($j) { $j } else { $e } } default { $e } } }
Add-Type -AssemblyName PresentationFramework

# 자기 자신이 설치 폴더 안에 있으면 지울 수 없으니, 임시 폴더에 복사해서 거기서 다시 실행한다
if (-not $FromTemp -and $PSScriptRoot -and ($PSScriptRoot.TrimEnd('\') -ieq $InstallDir.TrimEnd('\'))) {
    $tmp = Join-Path $env:TEMP ('dalu-uninstall-' + [guid]::NewGuid().ToString('N').Substring(0, 8) + '.ps1')
    Copy-Item $PSCommandPath $tmp -Force
    # Start-Process 는 배열 인자를 따옴표 없이 이어 붙인다: 공백이 든 경로(기본 설치 위치도 그렇다)는 직접 따옴표로 감싸야 한다
    function Q($v) { '"' + $v + '"' }
    $argList = '-NoProfile -ExecutionPolicy Bypass -File ' + (Q $tmp) + ' -InstallDir ' + (Q $InstallDir) + ' -StartMenuDir ' + (Q $StartMenuDir) + ' -RegistryRoot ' + (Q $RegistryRoot) + ' -RunKey ' + (Q $RunKey) + ' -DataDir ' + (Q $DataDir) + ' -FromTemp'
    if ($RemoveData) { $argList += ' -RemoveData' }
    if ($Quiet) { $argList += ' -Quiet' }
    Start-Process powershell.exe -ArgumentList $argList -WindowStyle Hidden
    exit 0
}

if (-not $Quiet) {
    $r = [System.Windows.MessageBox]::Show((T "$AppName 를 제거할까요?" "Uninstall $AppName?" "要卸载 $AppName 吗？" "$AppName をアンインストールしますか？"), $AppName, 'YesNo', 'Question')
    if ($r -ne 'Yes') { exit 0 }
    if (-not $RemoveData) {
        $r2 = [System.Windows.MessageBox]::Show((T "설정, 할 일, 가사 캐시 같은 내 데이터도 함께 지울까요?`n(아니요를 고르면 데이터는 남겨 두어 나중에 다시 설치해도 그대로 쓸 수 있어요.)" "Also delete your data (settings, to-dos, lyric cache)?`n(Choose No to keep it for a future reinstall.)" "是否同时删除你的数据（设置、待办、歌词缓存）？`n（选择“否”会保留数据，以后重新安装时可继续使用。）" "設定・タスク・歌詞キャッシュなどのデータも一緒に削除しますか？`n（「いいえ」を選ぶとデータは残り、再インストールしてもそのまま使えます。）"), $AppName, 'YesNo', 'Question')
        if ($r2 -eq 'Yes') { $RemoveData = $true }
    }
}

# 실행 중이면 끈다 (설치 폴더 안의 프로세스만)
$prefix = ($InstallDir.TrimEnd('\') + '\').ToLowerInvariant()
Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.ExecutablePath -and $_.ExecutablePath.ToLowerInvariant().StartsWith($prefix) } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep -Milliseconds 800

# 시작 프로그램 항목: 우리가 설치한 것을 가리킬 때만 지운다
try {
    $cur = (Get-ItemProperty -Path $RunKey -Name $RunName -ErrorAction Stop).$RunName
    if ($cur -and $cur.ToLowerInvariant().Contains($prefix)) { Remove-ItemProperty -Path $RunKey -Name $RunName -ErrorAction SilentlyContinue }
} catch {}
# 바로가기 / 제거 프로그램 등록
Remove-Item -Path (Join-Path $StartMenuDir "$AppName.lnk") -Force -ErrorAction SilentlyContinue
Remove-Item -Path (Join-Path $RegistryRoot $UninstallId) -Recurse -Force -ErrorAction SilentlyContinue
# 사용자 데이터
if ($RemoveData -and (Test-Path $DataDir)) { Remove-Item -Path $DataDir -Recurse -Force -ErrorAction SilentlyContinue }

# 설치 폴더는 이 스크립트가 끝난 뒤에 지운다 (PowerShell 이 쓰던 파일이 없으니 바로 지워도 되지만, 안전하게 잠깐 기다린다)
Start-Sleep -Milliseconds 300
Remove-Item -Path $InstallDir -Recurse -Force -ErrorAction SilentlyContinue
if (Test-Path $InstallDir) { Start-Process cmd.exe -ArgumentList ('/c ping -n 3 127.0.0.1 >nul & rmdir /s /q "' + $InstallDir + '"') -WindowStyle Hidden }
if (-not $Quiet) { [void][System.Windows.MessageBox]::Show((T '제거했어요.' 'Uninstalled.' '已卸载。' 'アンインストールしました。'), $AppName, 'OK', 'Information') }
if ($FromTemp) { Start-Process cmd.exe -ArgumentList ('/c ping -n 3 127.0.0.1 >nul & del /f /q "' + $PSCommandPath + '"') -WindowStyle Hidden }
