using System.Text.Json;
using System.Text.RegularExpressions;
using NotarAI.VirtualEmployee.Protocol;

namespace NotarAI.VirtualEmployee.Probe;

/// <summary>
/// Filesystem-only *synthetic* transport. No network, no raw command execution.
/// A future authenticated transport must preserve this admission boundary.
/// </summary>
internal sealed class LocalInboxProcessor
{
    private static readonly Regex JobId = new(@"\A[a-f0-9]{32}\z", RegexOptions.CultureInvariant);
    private readonly string _inbox;
    private readonly string _outbox;
    private readonly string _tenant;
    private readonly byte[] _key;
    private readonly FileReplayGuard _replay;

    public LocalInboxProcessor(string tenant, byte[] key, string inbox, string outbox, string replay)
    {
        _inbox = SafeDirectory(inbox);
        _outbox = SafeDirectory(outbox);
        _tenant = tenant;
        _key = key;
        _replay = new FileReplayGuard(SafeDirectory(replay));
        if (string.Equals(_inbox, _outbox, StringComparison.OrdinalIgnoreCase))
            throw new ArgumentException("Inbox and outbox cannot be the same directory");
    }

    public int Drain(Func<string, int> execute)
    {
        var handled = 0;
        foreach (var candidate in Directory.EnumerateFiles(_inbox, "*.json").Take(100))
        {
            var jobId = Path.GetFileNameWithoutExtension(candidate);
            if (!JobId.IsMatch(jobId))
                continue; // Strict filenames, never user-provided path segments.
            var output = Path.Combine(_outbox, jobId + ".status.json");
            if (File.Exists(output))
                continue;
            string status;
            string code;
            try
            {
                if ((File.GetAttributes(candidate) & FileAttributes.ReparsePoint) != 0)
                    continue;
                if (new FileInfo(candidate).Length > 4096)
                {
                    status = "rejected";
                    code = "oversize";
                }
                else
                {
                    var json = File.ReadAllText(candidate);
                    // An attacker cannot replay one job under a different file ID.
                    SignedJob? parsed;
                    try { parsed = JobAdmission.ParseStrict(json); }
                    catch (Exception ex) when (ex is JsonException or InvalidOperationException or FormatException or OverflowException)
                    {
                        parsed = null;
                    }
                    if (parsed is null)
                    {
                        status = "rejected";
                        code = "malformed";
                    }
                    else if (!string.Equals(parsed.JobId, jobId, StringComparison.Ordinal))
                    {
                        status = "rejected";
                        code = "job_id_mismatch";
                    }
                    else
                    {
                        var result = JobAdmission.Admit(json, _tenant, _key, DateTimeOffset.UtcNow, _replay);
                        status = result.Allowed ? "accepted" : "rejected";
                        code = result.Code;
                        if (result.Allowed)
                        {
                            int exitCode;
                            try { exitCode = execute(result.Operation!); }
                            catch (Exception)
                            {
                                // No exception text or UI data in logs or result files.
                                exitCode = 5;
                            }
                            status = exitCode == 0 ? "completed" : "failed";
                            code = exitCode == 0 ? "probe_success" : "probe_failed";
                        }
                    }
                }
                WriteOutcome(output, jobId, status, code);
                handled++;
            }
            catch (IOException)
            {
                // Do not print file contents, secrets, titles or names.
                Console.Error.WriteLine("Local inbox I/O unavailable");
            }
            catch (UnauthorizedAccessException)
            {
                Console.Error.WriteLine("Local inbox permission denied");
            }
        }
        return handled;
    }

    private static string SafeDirectory(string path)
    {
        var full = Path.GetFullPath(path);
        if (!Directory.Exists(full))
            throw new DirectoryNotFoundException("Pre-provision private agent directories");
        if ((File.GetAttributes(full) & FileAttributes.ReparsePoint) != 0)
            throw new InvalidOperationException("Reparse-point directories are not permitted");
        return full;
    }

    internal static void WriteOutcome(string path, string jobId, string status, string code)
    {
        var json = JsonSerializer.Serialize(new
        {
            jobId,
            status,
            code,
            atUtc = DateTimeOffset.UtcNow.ToString("O")
        });
        var tmp = path + "." + Guid.NewGuid().ToString("N") + ".tmp";
        try
        {
            File.WriteAllText(tmp, json);
            File.Move(tmp, path, overwrite: false);
        }
        finally
        {
            if (File.Exists(tmp)) File.Delete(tmp);
        }
    }
}
