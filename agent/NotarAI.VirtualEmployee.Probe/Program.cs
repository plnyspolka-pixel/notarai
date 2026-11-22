// Local-only diagnostic runner. No network listener, browser agent,
// arbitrary command execution, file-content extraction or RejNET actions.
using System.Diagnostics;
using System.Security.Cryptography;
using Amazon;
using Amazon.Runtime;
using Amazon.SQS;
using FlaUI.Core.Definitions;
using FlaUI.Core.AutomationElements;
using FlaUI.UIA3;
using NotarAI.VirtualEmployee.Protocol;
using NotarAI.VirtualEmployee.Probe;

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
if (args.Length == 2 && args[0] == "--survey-ui")
    return SurveyControlTypes(args[1]);
if (args.Length == 1 && args[0] == "--once-local-inbox")
    return RunLocalInbox(continuous: false);
if (args.Length == 1 && args[0] == "--serve-local-inbox")
    return RunLocalInbox(continuous: true);
if (args.Length == 1 && args[0] == "--once-sqs")
    return await RunSqs(continuous: false);
if (args.Length == 1 && args[0] == "--serve-sqs")
    return await RunSqs(continuous: true);
if (args.Length != 2 || args[0] != "--run-verified-local-job")
{
    Console.WriteLine("Usage: --session-health | --inspect-notepad | --survey-ui <PID> | --run-verified-local-job <job.json> | --once-local-inbox | --serve-local-inbox | --once-sqs | --serve-sqs");
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

// For the vendor qualification workshop only. Returns a histogram of
// UIA control *types* in the current user's session. Never reads Name, Value,
// text, window title, automation IDs or document content.
static int SurveyControlTypes(string rawPid)
{
    if (!int.TryParse(rawPid, out var pid) || pid <= 0)
        return 2;
    try
    {
        using var target = Process.GetProcessById(pid);
        if (target.SessionId != Process.GetCurrentProcess().SessionId)
        {
            Console.Error.WriteLine("Target must belong to the current desktop session");
            return 7;
        }
        using var automation = new UIA3Automation();
        var roots = automation.GetDesktop()
            .FindAllChildren(cf => cf.ByControlType(ControlType.Window));
        const int maxElements = 400;
        const int maxDepth = 4;
        var truncated = false;
        var counts = new Dictionary<ControlType, int>();
        var queue = new Queue<(AutomationElement Element, int Depth)>();
        foreach (var root in roots)
        {
            try
            {
                if (root.Properties.ProcessId.Value == pid)
                {
                    if (queue.Count < maxElements) queue.Enqueue((root, 0));
                    else truncated = true;
                }
            }
            catch (Exception ex) when (ex is System.Runtime.InteropServices.COMException or InvalidOperationException)
            {
                // Window disappeared.
            }
        }
        var inspected = 0;
        while (queue.Count > 0 && inspected < maxElements)
        {
            var (element, depth) = queue.Dequeue();
            try
            {
                var controlType = element.Properties.ControlType.Value;
                counts[controlType] = counts.GetValueOrDefault(controlType) + 1;
                inspected++;
                if (depth < maxDepth)
                {
                    foreach (var child in element.FindAllChildren())
                    {
                        if (queue.Count + inspected >= maxElements) { truncated = true; break; }
                        queue.Enqueue((child, depth + 1));
                    }
                }
            }
            catch (Exception ex) when (ex is System.Runtime.InteropServices.COMException or InvalidOperationException)
            {
                // Stale UIA element; ignore without printing its properties.
            }
        }
        Console.WriteLine($"Read-only UIA type histogram; inspected: {inspected}; truncated: {truncated || queue.Count > 0}");
        foreach (var type in counts.Keys.OrderBy(x => x.ToString(), StringComparer.Ordinal))
            Console.WriteLine($"{type}: {counts[type]}");
        return inspected > 0 ? 0 : 5;
    }
    catch (Exception ex) when (ex is ArgumentException or InvalidOperationException or
                                System.ComponentModel.Win32Exception or
                                System.Runtime.InteropServices.COMException)
    {
        Console.Error.WriteLine("UIA target not available");
        return 5;
    }
}

static int RunLocalInbox(bool continuous)
{
    var tenant = Environment.GetEnvironmentVariable("NOTARAI_VE_TENANT_ID");
    var keyFile = Environment.GetEnvironmentVariable("NOTARAI_VE_HMAC_KEY_FILE");
    var inbox = Environment.GetEnvironmentVariable("NOTARAI_VE_INBOX_DIR");
    var outbox = Environment.GetEnvironmentVariable("NOTARAI_VE_OUTBOX_DIR");
    var replay = Environment.GetEnvironmentVariable("NOTARAI_VE_REPLAY_DIR");
    if (string.IsNullOrWhiteSpace(tenant) || string.IsNullOrWhiteSpace(keyFile) ||
        string.IsNullOrWhiteSpace(inbox) || string.IsNullOrWhiteSpace(outbox) ||
        string.IsNullOrWhiteSpace(replay))
    {
        Console.Error.WriteLine("Missing local inbox configuration");
        return 6;
    }
    byte[] key = [];
    try
    {
        key = File.ReadAllBytes(keyFile);
        var worker = new LocalInboxProcessor(tenant, key, inbox, outbox, replay);
        if (!continuous)
        {
            worker.Drain(ExecuteDiagnosticOperation);
            return 0;
        }
        Console.WriteLine("Local diagnostic worker active in interactive session only");
        // Process exits when the interactive user logs off. No auto-logon.
        while (true)
        {
            worker.Drain(ExecuteDiagnosticOperation);
            Thread.Sleep(TimeSpan.FromSeconds(3));
        }
    }
    catch (Exception ex) when (ex is IOException or UnauthorizedAccessException or
                                InvalidOperationException or ArgumentException)
    {
        Console.Error.WriteLine("Local worker configuration or I/O unavailable");
        return 6;
    }
    finally { CryptographicOperations.ZeroMemory(key); }
}

// This optional transport is only enabled explicitly after the separate
// SQS pilot stack is provisioned. No static AWS credentials are stored.
static async Task<int> RunSqs(bool continuous)
{
    var tenant = Environment.GetEnvironmentVariable("NOTARAI_VE_TENANT_ID");
    var keyPath = Environment.GetEnvironmentVariable("NOTARAI_VE_HMAC_KEY_FILE");
    var replay = Environment.GetEnvironmentVariable("NOTARAI_VE_REPLAY_DIR");
    var outbox = Environment.GetEnvironmentVariable("NOTARAI_VE_OUTBOX_DIR");
    var queueUrl = Environment.GetEnvironmentVariable("NOTARAI_VE_SQS_QUEUE_URL");
    if (string.IsNullOrWhiteSpace(tenant) || string.IsNullOrWhiteSpace(keyPath) ||
        string.IsNullOrWhiteSpace(replay) || string.IsNullOrWhiteSpace(outbox) ||
        string.IsNullOrWhiteSpace(queueUrl) ||
        !SqsDiagnosticPoller.ValidQueueUrl(queueUrl, tenant))
    {
        Console.Error.WriteLine("SQS pilot configuration missing or invalid");
        return 6;
    }
    // Never accept static AWS credentials in the operator environment.
    if (!string.IsNullOrWhiteSpace(Environment.GetEnvironmentVariable("AWS_ACCESS_KEY_ID")) ||
        !string.IsNullOrWhiteSpace(Environment.GetEnvironmentVariable("AWS_PROFILE")))
    {
        Console.Error.WriteLine("SQS worker requires EC2 role credentials, not AWS environment overrides");
        return 6;
    }
    byte[] key = [];
    try
    {
        key = File.ReadAllBytes(keyPath);
        using var vmCredentials = new InstanceProfileAWSCredentials();
        using var sqs = new AmazonSQSClient(vmCredentials, RegionEndpoint.EUCentral1);
        var poller = new SqsDiagnosticPoller(sqs, queueUrl, tenant, key, replay, outbox);
        do
        {
            await poller.PollOnceAsync(ExecuteDiagnosticOperation, CancellationToken.None);
        }
        while (continuous);
        return 0;
    }
    catch (Exception ex) when (ex is IOException or UnauthorizedAccessException or
        InvalidOperationException or ArgumentException or AmazonServiceException)
    {
        // Do not print AWS request details, message bodies, tenant data, or secret files.
        Console.Error.WriteLine("Private SQS diagnostic channel unavailable");
        return 6;
    }
    finally
    {
        CryptographicOperations.ZeroMemory(key);
    }
}

static int ExecuteDiagnosticOperation(string operation) => operation switch
{
    "probe.session" => ReportSession(),
    "probe.notepad" => InspectNotepad(),
    _ => 7
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
