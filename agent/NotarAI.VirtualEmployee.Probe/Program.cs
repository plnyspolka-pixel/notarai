// Synthetic, read-only UIA3 pilot. Never enumerates window titles or document text.
using System.Diagnostics;
using FlaUI.Core.Definitions;
using FlaUI.UIA3;

if (!OperatingSystem.IsWindows())
{
    Console.Error.WriteLine("Windows is required");
    return 2;
}
if (args.Length != 1 || args[0] != "--inspect-notepad")
{
    Console.WriteLine("Usage: NotarAI.VirtualEmployee.Probe --inspect-notepad");
    return 2;
}
if (!Environment.UserInteractive || Process.GetCurrentProcess().SessionId == 0)
{
    Console.Error.WriteLine("Interactive non-Session-0 Windows session required");
    return 3;
}
// The first test is deliberately restricted to Windows Notepad; not RejNET.
using var automation = new UIA3Automation();
using var ownedProcesses = new ProcessCollection(Process.GetProcessesByName("notepad"));
var pids = new HashSet<int>(ownedProcesses.ProcessIds);
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
        // Windows may close during enumeration; do not log UI data.
    }
}
Console.WriteLine($"Session OK; active Notepad windows discovered: {matching}");
return matching > 0 ? 0 : 5;

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
