# Dalu — 개인정보 / Privacy / 隐私 / プライバシー

## 한국어

**Dalu 는 계정도, 서버도, 분석(통계) 수집도 없습니다.** 설정·할 일·물 기록·파일 선반·로그는 모두 내 PC 의 `%APPDATA%\Dalu` 에만 저장되고, 개발자에게 아무것도 전송되지 않습니다.

앱이 인터넷으로 나가는 경우는 아래뿐입니다(모두 내가 켠 기능일 때만, 설정에서 끌 수 있습니다).

| 언제 | 어디로 | 무엇을 보내나 |
| --- | --- | --- |
| Cider 가 아닌 앱(Spotify·브라우저 등)의 곡 가사 찾기 (설정 › 음악 › "다른 앱의 음악" › "외부 가사 검색", 기본 켜짐) | `lrclib.net`, `music.163.com`(NetEase, 중국) | **곡 제목, 아티스트, 앨범, 곡 길이**. 이 외의 개인 정보는 보내지 않습니다. 끄면 외부로 나가지 않습니다. |
| 캘린더 일정 보기 (설정에서 .ics 주소를 직접 넣었을 때만) | 내가 넣은 주소 | 일반적인 HTTP 요청(내 주소 요청). 주소는 PC 에만 저장됩니다. |
| WebView2 런타임 설치(없을 때, 설치 중 "예"를 눌렀을 때만) | Microsoft 공식 서버 | Microsoft 설치 프로그램 내려받기 |
| 웹 바로가기 플러그인·"가사 찾기" 버튼 등을 눌렀을 때 | 기본 브라우저가 해당 사이트(Google, YouTube, Genius 등)를 엽니다 | 브라우저가 평소처럼 요청합니다 |

그 밖에:
- Cider(`127.0.0.1:10767`)와는 **내 PC 안에서만** 통신합니다. Apple Music 가사는 내 PC 의 Cider 가 대신 조회하며, Dalu 가 Apple 서버에 직접 접속하지는 않습니다.
- 클립보드 기록은 기본으로 꺼져 있고, 켜도 메모리에만 있으며 저장되지 않습니다.
- 윈도우 알림 동그라미(설정에서 켰을 때만): 새 알림이 왔는지와 **앱 이름**만 봅니다. 알림의 제목·내용은 읽지도 저장하지도 않습니다. 설정에서 앱별로 끌 수 있도록 알림을 보낸 앱의 이름과 횟수를 `%APPDATA%\Dalu\island\winnotif_apps.json` 에 이 PC 안에만 기억합니다(지우면 다시 쌓입니다).
- 가사는 각 서비스의 것이며, 앱은 가사를 따로 보관하지 않습니다(재조회를 줄이기 위한 캐시만 `%APPDATA%\Dalu\lyrics_cache` 에 둡니다. 설정에서 지울 수 있습니다).
- 앱 로그(`%APPDATA%\Dalu\island\app.log`)는 내 PC 에만 있습니다. 문제를 신고할 때 원하는 부분만 골라 보내 주세요.

## English

**Dalu has no accounts, no servers and no analytics/telemetry.** Settings, to-dos, water log, file shelf and logs are stored only on your PC in `%APPDATA%\Dalu`. Nothing is sent to the developer.

The app only goes online in these cases (only if you use the feature; you can turn it off in Settings):

| When | Where | What is sent |
| --- | --- | --- |
| Finding lyrics for apps other than Cider (Settings › Music › "Other apps" › "Search lyrics online", on by default) | `lrclib.net`, `music.163.com` (NetEase, China) | **Track title, artist, album and duration** — nothing else personal. Turn it off and nothing leaves your PC. |
| Calendar agenda (only if you paste an .ics URL yourself) | The URL you entered | A normal HTTP request to that URL. The URL is stored only on your PC. |
| WebView2 runtime install (only if missing and you click "Yes" during setup) | Microsoft's official servers | Downloads Microsoft's installer |
| Clicking web-shortcut plugins / "Find lyrics" etc. | Your default browser opens the site (Google, YouTube, Genius, ...) | Your browser makes the usual request |

Also:
- Cider (`127.0.0.1:10767`) is contacted **only on your own PC**. Apple Music lyrics are looked up by your local Cider; Dalu never connects to Apple servers itself.
- Clipboard history is off by default; when on, it lives in memory only and is never saved.
- Windows notification circle (only if you turn it on): the app only sees that a new notification arrived and the **app name** — never the title or text. To let you switch apps off one by one in Settings, it remembers the names of apps that sent notifications and how many, in `%APPDATA%\Dalu\island\winnotif_apps.json` on your PC only (delete it and it fills up again).
- Lyrics belong to their services; the app keeps only a cache to avoid repeat lookups in `%APPDATA%\Dalu\lyrics_cache` (clearable in Settings).
- The app log (`%APPDATA%\Dalu\island\app.log`) stays on your PC. When reporting a problem, send only the parts you are comfortable sharing.

## 简体中文

**Dalu 没有账号、没有服务器，也不收集任何统计数据。** 设置、待办、饮水记录、文件架和日志都只保存在你电脑的 `%APPDATA%\Dalu` 中，不会向开发者发送任何内容。

应用只在以下情况联网（仅在你使用该功能时，可在设置中关闭）：

| 何时 | 去哪里 | 发送什么 |
| --- | --- | --- |
| 为 Cider 以外的应用（Spotify、浏览器等）查找歌词（设置 › 音乐 › “其他应用（Spotify、浏览器等）” › “在线搜索歌词”，默认开启） | `lrclib.net`、`music.163.com`（网易云音乐，中国） | **歌曲名、歌手、专辑和时长**，不含其他个人信息。关闭后不会向外发送。 |
| 日历日程（仅当你自己填写 .ics 地址时） | 你填写的地址 | 对该地址的普通 HTTP 请求。地址仅保存在你的电脑上。 |
| 安装 WebView2 运行时（仅在缺少且你在安装时点“是”） | Microsoft 官方服务器 | 下载 Microsoft 的安装程序 |
| 点击网页快捷方式插件、“查找歌词”等按钮 | 默认浏览器打开对应网站（Google、YouTube、Genius 等） | 浏览器照常发出请求 |

另外：
- 与 Cider（`127.0.0.1:10767`）**只在你自己的电脑内**通信。Apple Music 歌词由你电脑上的 Cider 代为查询，Dalu 本身不会直接连接 Apple 服务器。
- 剪贴板历史默认关闭；开启后只存在内存中，不会保存。
- Windows 通知小圆点（仅在你开启时）：只会知道是否有新通知以及**应用名称**，不会读取通知的标题和内容。为了让你能在设置中逐个关闭应用，会把发送过通知的应用名称和次数只保存在你电脑上的 `%APPDATA%\Dalu\island\winnotif_apps.json`（删除后会重新积累）。
- 歌词归各服务所有；应用只在 `%APPDATA%\Dalu\lyrics_cache` 保留避免重复查询的缓存（可在设置中清除）。
- 应用日志（`%APPDATA%\Dalu\island\app.log`）只在你的电脑上。反馈问题时，请只发送你愿意分享的部分。

## 日本語

**Dalu にはアカウントも、サーバーも、利用状況の収集もありません。** 設定・やること・水分記録・ファイル棚・ログは、すべてお使いの PC の `%APPDATA%\Dalu` にだけ保存され、開発者には何も送られません。

アプリがインターネットに接続するのは次の場合だけです（その機能を使うときのみ。設定でオフにできます）。

| いつ | どこへ | 何を送るか |
| --- | --- | --- |
| Cider 以外のアプリ（Spotify・ブラウザーなど）の歌詞検索（設定 › 音楽 › 「他のアプリ（Spotify、ブラウザーなど）」 › 「オンラインで歌詞を検索」、既定でオン） | `lrclib.net`、`music.163.com`（NetEase、中国） | **曲名・アーティスト・アルバム・曲の長さ**のみ。それ以外の個人情報は送りません。オフにすると外部へ送られません。 |
| カレンダーの予定（自分で .ics のアドレスを入れたときだけ） | 入力したアドレス | そのアドレスへの通常の HTTP リクエスト。アドレスは PC にだけ保存されます。 |
| WebView2 ランタイムのインストール（未導入で、セットアップ中に「はい」を選んだときだけ） | Microsoft の公式サーバー | Microsoft のインストーラーのダウンロード |
| ウェブショートカットのプラグインや「歌詞を探す」などを押したとき | 既定のブラウザーがそのサイト（Google、YouTube、Genius など）を開きます | ブラウザーがいつもどおりリクエストします |

そのほか：
- Cider（`127.0.0.1:10767`）とは**お使いの PC の中だけ**で通信します。Apple Music の歌詞は PC 上の Cider が代わりに検索し、Dalu が Apple のサーバーへ直接接続することはありません。
- クリップボード履歴は既定でオフです。オンにしてもメモリ上だけで、保存されません。
- Windows 通知の丸（オンにしたときだけ）：新しい通知が来たことと**アプリ名**だけを見ます。通知のタイトルや本文は読みも保存もしません。設定でアプリごとにオフにできるよう、通知を送ったアプリの名前と回数を、お使いの PC 内の `%APPDATA%\Dalu\island\winnotif_apps.json` にだけ記憶します（削除すると、また溜まります）。
- 歌詞は各サービスのものです。アプリは再検索を減らすためのキャッシュだけを `%APPDATA%\Dalu\lyrics_cache` に置きます（設定で削除できます）。
- アプリのログ（`%APPDATA%\Dalu\island\app.log`）は PC にだけあります。問題を報告するときは、共有してよい部分だけを送ってください。
