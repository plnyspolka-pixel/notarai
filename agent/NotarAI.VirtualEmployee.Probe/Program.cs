// Local-only diagnostic runner. No network listener, browser agent,
// arbitrary command execution, file-content extraction or RejNET actions.
using System.Diagnostics;
using System.Security.Cryptography;
using FlaUI.Core.Definitions;
using FlaUI.UIA3;
using NotarAI.VirtualEmployee.Protocol;

if (!OperatingSystem.IsWindows())
{
    Console.Error.WriteLine("Windows is required");
    return 2;
}
if (!Environment.UserInteractive || Process.GetCurrentProcess().SessionId == 0)
{
    Console.Error.WriteLine("Interactive non-Session-0 Windows session required");
    return 3;
}
if (args.Length == 1 && args[0] == "--session-health")
    return ReportSession();
if (args.Length == 1 && args[0] == "--inspect-notepad")
    return InspectNotepad();
if (args.Length != 2 || args[0] != "--run-verified-local-job")
{
    Console.WriteLine("Usage: --session-health OR --inspect-notepad OR --run-verified-local-job <local-job.json>");
    return 2;
}

var tenant = Environment.GetEnvironmentVariable("NOTARAI_VE_TENANT_ID");
var keyPath = Environment.GetEnvironmentVariable("NOTARAI_VE_HMAC_KEY_FILE");
var replayDir = Environment.GetEnvironmentVariable("NOTARAI_VE_REPLAY_DIR");
if (string.IsNullOrWhiteSpace(tenant) ||
    string.IsNullOrWhiteSpace(keyPath) ||
    string.IsNullOrWhiteSpace(replayDir))
{
    Console.Error.WriteLine("Missing local agent configuration");
    return 6;
}

AdmissionResult admission;
byte[] secret = [];
try
{
    // The operator must provision a binary 32+ byte key, protected with
    // restrictive Windows ACLs. Never accept keys on the command line.
    secret = File.ReadAllBytes(keyPath);
    var json = File.ReadAllText(args[1]);
    var replay = new FileReplayGuard(replayDir);
    admission = JobAdmission.Admit(json, tenant, secret, DateTimeOffset.UtcNow, replay);
}
catch (Exception ex) when (ex is IOException or UnauthorizedAccessException or
                            InvalidOperationException or DirectoryNotFoundException)
{
    Console.Error.WriteLine("Local job or agent configuration unavailable");
    return 6;
}
finally
{
    CryptographicOperations.ZeroMemory(secret);
}
if (!admission.Allowed)
{
    Console.Error.WriteLine("Job rejected: " + admission.Code);
    return 7;
}

return admission.Operation switch
{
    "probe.session" => ReportSession(),
    "probe.notepad" => InspectNotepad(),
    _ => 7 // Defense-in-depth; never accept shell/script actions.
};

static int ReportSession()
{
    Console.WriteLine("Interactive session available; no application data accessed");
    return 0;
}

static int InspectNotepad()
{
    try
    {
        using var automation = new UIA3Automation();
        using var owned = new ProcessCollection(Process.GetProcessesByName("notepad"));
        var pids = new HashSet<int>(owned.ProcessIds);
        if (pids.Count == 0)
        {
            Console.WriteLine("Notepad not running (open Notepad and retry)");
            return 4;
        }
        var desktop = automation.GetDesktop();
        var windows = desktop.FindAllChildren(cf => cf.ByControlType(ControlType.Window));
        var matching = 0;
        foreach (var window in windows)
        {
            try
            {
                if (pids.Contains(window.Properties.ProcessId.Value)) matching++;
            }
            catch (Exception ex) when (ex is System.Runtime.InteropServices.COMException or InvalidOperationException)
            {
                // A window closed during enumeration. No screen text is logged.
            }
        }
        Console.WriteLine($"Session OK; active Notepad windows discovered: {matching}");
        return matching > 0 ? 0 : 5;
    }
    catch (Exception ex) when (ex is System.Runtime.InteropServices.COMException or InvalidOperationException)
    {
        Console.Error.WriteLine("UI Automation unavailable in this session");
        return 5;
    }
}

internal sealed class ProcessCollection : IDisposable
{
    private readonly Process[] _processes;
    public ProcessCollection(Process[] processes) => _processes = processes;
    public IEnumerable<int> ProcessIds => _processes.Select(process => process.Id);
    public void Dispose()
    {
        foreach (var process in _processes) process.Dispose();
    }
}
