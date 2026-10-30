// Dalu 설치 프로그램(Setup.exe)의 껍데기.
// 안에 payload.zip(런타임 + 앱 + 설치 스크립트)이 리소스로 들어 있다. 임시 폴더에 풀고 install.ps1 을 실행한 뒤 정리한다.
// 받은 명령줄 인자는 그대로 install.ps1 에 넘긴다 (예: -Quiet -NoLaunch -InstallDir "D:\Apps\DI").
// C# 5(.NET Framework 4.x 에 들어 있는 csc.exe)로 컴파일되므로 최신 문법은 쓰지 않는다.
using System;
using System.Diagnostics;
using System.Drawing;
using System.Globalization;
using System.IO;
using System.IO.Compression;
using System.Reflection;
using System.Text;
using System.Threading;
using System.Windows.Forms;

[assembly: AssemblyTitle("Dalu Setup")]
[assembly: AssemblyProduct("Dalu")]
[assembly: AssemblyVersion("@VERSION@.0")]
[assembly: AssemblyFileVersion("@VERSION@.0")]

static class Setup
{
    static string Lang { get { return CultureInfo.CurrentUICulture.TwoLetterISOLanguageName; } }
    // ko / zh / ja, 그 밖은 영어 (zh, ja 를 주지 않은 문구는 영어)
    static string T(string ko, string en, string zh, string ja)
    {
        switch (Lang) { case "ko": return ko; case "zh": return zh ?? en; case "ja": return ja ?? en; default: return en; }
    }

    static string Quote(string a)
    {
        if (a.Length > 0 && a.IndexOfAny(new[] { ' ', '\t', '"' }) < 0) return a;
        return "\"" + a.Replace("\"", "\\\"") + "\"";
    }

    [STAThread]
    static int Main(string[] args)
    {
        bool quiet = false;
        foreach (string a in args) if (string.Equals(a, "-Quiet", StringComparison.OrdinalIgnoreCase)) quiet = true;
        string work = Path.Combine(Path.GetTempPath(), "Dalu-" + Guid.NewGuid().ToString("N").Substring(0, 8));
        int code = 0;
        string error = null;
        Form form = null;
        Label label = null;
        if (!quiet)
        {
            Application.EnableVisualStyles();
            form = new Form();
            form.Text = "Dalu";
            form.FormBorderStyle = FormBorderStyle.FixedDialog;
            form.StartPosition = FormStartPosition.CenterScreen;
            form.ControlBox = false;
            form.MaximizeBox = false;
            form.MinimizeBox = false;
            form.ShowInTaskbar = true;
            form.ClientSize = new Size(380, 96);
            label = new Label();
            label.Text = T("설치 준비 중...", "Preparing the installer...", "正在准备安装…", "インストールの準備中…");
            label.AutoSize = false;
            label.SetBounds(18, 16, 344, 24);
            ProgressBar bar = new ProgressBar();
            bar.Style = ProgressBarStyle.Marquee;
            bar.MarqueeAnimationSpeed = 30;
            bar.SetBounds(18, 50, 344, 18);
            form.Controls.Add(label);
            form.Controls.Add(bar);
            try { form.Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath); } catch (Exception) { }
        }

        Thread worker = new Thread(delegate ()
        {
            try
            {
                Directory.CreateDirectory(work);
                string zip = Path.Combine(work, "payload.zip");
                using (Stream s = Assembly.GetExecutingAssembly().GetManifestResourceStream("payload.zip"))
                {
                    if (s == null) throw new InvalidOperationException("payload.zip is missing from this installer.");
                    using (FileStream f = File.Create(zip)) s.CopyTo(f);
                }
                string dir = Path.Combine(work, "files");
                ZipFile.ExtractToDirectory(zip, dir);
                File.Delete(zip);
                string script = Path.Combine(Path.Combine(dir, "Dalu"), "install.ps1");
                StringBuilder sb = new StringBuilder("-NoProfile -ExecutionPolicy Bypass -File " + Quote(script));
                foreach (string a in args) sb.Append(' ').Append(Quote(a));
                if (form != null) form.Invoke((MethodInvoker)delegate { label.Text = T("설치하는 중...", "Installing...", "正在安装…", "インストール中…"); form.Hide(); });
                ProcessStartInfo psi = new ProcessStartInfo("powershell.exe", sb.ToString());
                psi.UseShellExecute = false;
                psi.CreateNoWindow = true;
                using (Process p = Process.Start(psi))
                {
                    p.WaitForExit();
                    code = p.ExitCode;
                }
            }
            catch (Exception e)
            {
                error = e.Message;
                code = 1;
            }
            finally
            {
                try { if (Directory.Exists(work)) Directory.Delete(work, true); } catch (Exception) { }
                if (form != null) { try { form.Invoke((MethodInvoker)delegate { form.Close(); }); } catch (Exception) { } }
            }
        });
        worker.IsBackground = false;
        worker.SetApartmentState(ApartmentState.STA);
        worker.Start();
        if (form != null) Application.Run(form);
        worker.Join();
        if (error != null && !quiet)
            MessageBox.Show(T("설치 파일을 처리하지 못했어요: ", "Could not process the installer: ", "无法处理安装文件：", "インストールファイルを処理できませんでした：") + error, "Dalu Setup", MessageBoxButtons.OK, MessageBoxIcon.Error);
        return code;
    }
}
