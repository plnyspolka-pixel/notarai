using System.Text.Json;
using NotarAI.VirtualEmployee.Protocol;
using NotarAI.VirtualEmployee.Probe;

var failures = new List<string>();
var checkedCount = 0;
var now = DateTimeOffset.FromUnixTimeSeconds(1_800_000_000);
var secret = Enumerable.Range(0, 32).Select(x => (byte)x).ToArray();
const string tenant = "pilot01";
var job = new SignedJob(
    1, tenant, "0123456789abcdef0123456789abcdef", "probe.session",
    now.ToUnixTimeSeconds() - 10, now.ToUnixTimeSeconds() + 50,
    "abcdef0123456789abcdef0123456789", "");
var opt = new JsonSerializerOptions { PropertyNamingPolicy = JsonNamingPolicy.CamelCase };
string Json(SignedJob x) => JsonSerializer.Serialize(x, opt);
var signed = job with { Signature = JobAdmission.SignForTest(job, secret) };

void Check(string label, bool condition)
{
    checkedCount++;
    if (!condition) failures.Add(label);
}
Check("cross-language canonical signature", signed.Signature == "3001f34ea8457f39c5da9142fc6c2e2680956f5484a32082c030736c819ba7f0");
Check("valid fixture", JobAdmission.Admit(Json(signed), tenant, secret, now, new MemoryGuard()).Allowed);
var replay = new MemoryGuard();
Check("first claim", JobAdmission.Admit(Json(signed), tenant, secret, now, replay).Allowed);
Check("durable duplicate", JobAdmission.Admit(Json(signed), tenant, secret, now, replay).Code == "duplicate");
Check("wrong tenant", JobAdmission.Admit(Json(signed), "other01", secret, now, new MemoryGuard()).Code == "tenant_mismatch");
Check("bad signature", JobAdmission.Admit(Json(signed with { Operation = "probe.notepad" }), tenant, secret, now, new MemoryGuard()).Code == "bad_signature");
var forbidden = job with { Operation = "shell.execute", Signature = "" };
forbidden = forbidden with { Signature = JobAdmission.SignForTest(forbidden, secret) };
Check("forbidden signed operation", JobAdmission.Admit(Json(forbidden), tenant, secret, now, new MemoryGuard()).Code == "operation_denied");
var expired = job with { ExpiresAtUnix = now.ToUnixTimeSeconds() - 1, Signature = "" };
expired = expired with { Signature = JobAdmission.SignForTest(expired, secret) };
Check("expired", JobAdmission.Admit(Json(expired), tenant, secret, now, new MemoryGuard()).Code == "expired_or_invalid_time");
var future = job with { IssuedAtUnix = now.ToUnixTimeSeconds() + 120, ExpiresAtUnix = now.ToUnixTimeSeconds() + 150, Signature = "" };
future = future with { Signature = JobAdmission.SignForTest(future, secret) };
Check("clock skew", JobAdmission.Admit(Json(future), tenant, secret, now, new MemoryGuard()).Code == "expired_or_invalid_time");
Check("unknown JSON field", JobAdmission.Admit(Json(signed).TrimEnd('}') + ",\"payload\":\"secret\"}", tenant, secret, now, new MemoryGuard()).Code == "malformed");
Check("duplicate JSON field", JobAdmission.Admit(Json(signed).TrimEnd('}') + ",\"tenantId\":\"pilot01\"}", tenant, secret, now, new MemoryGuard()).Code == "malformed");
Check("oversized input", JobAdmission.Admit(new string('x', 5000), tenant, secret, now, new MemoryGuard()).Code == "malformed");
Check("short key", JobAdmission.Admit(Json(signed), tenant, new byte[8], now, new MemoryGuard()).Code == "invalid_configuration");
var jumbo = job with { IssuedAtUnix = long.MinValue, ExpiresAtUnix = long.MaxValue, Signature = "" };
jumbo = jumbo with { Signature = JobAdmission.SignForTest(jumbo, secret) };
Check("overflow time", JobAdmission.Admit(Json(jumbo), tenant, secret, now, new MemoryGuard()).Code == "expired_or_invalid_time");

var directory = Path.Combine(Path.GetTempPath(), "notarai-ve-protocol-" + Guid.NewGuid().ToString("N"));
Directory.CreateDirectory(directory);
try
{
    var guard = new FileReplayGuard(directory);
    Check("file first claim", guard.TryClaim(job.JobId));
    var guardAfterRestart = new FileReplayGuard(directory);
    Check("file replay denial after restart", !guardAfterRestart.TryClaim(job.JobId));
    Check("replay file count", Directory.GetFiles(directory, "*.claimed").Length == 1);
}
finally { Directory.Delete(directory, recursive: true); }


var spoolRoot = Path.Combine(Path.GetTempPath(), "notarai-ve-spool-" + Guid.NewGuid().ToString("N"));
Directory.CreateDirectory(spoolRoot);
try
{
    var inbox = Path.Combine(spoolRoot, "inbox");
    var outbox = Path.Combine(spoolRoot, "outbox");
    var replayDir = Path.Combine(spoolRoot, "replay");
    Directory.CreateDirectory(inbox);
    Directory.CreateDirectory(outbox);
    Directory.CreateDirectory(replayDir);
    var spoolNow = DateTimeOffset.UtcNow;
    var spoolJob = job with
    {
        JobId = "11111111111111111111111111111111",
        IssuedAtUnix = spoolNow.ToUnixTimeSeconds() - 5,
        ExpiresAtUnix = spoolNow.ToUnixTimeSeconds() + 50,
        Signature = ""
    };
    spoolJob = spoolJob with { Signature = JobAdmission.SignForTest(spoolJob, secret) };
    File.WriteAllText(Path.Combine(inbox, spoolJob.JobId + ".json"), Json(spoolJob));
    var worker = new LocalInboxProcessor(tenant, secret, inbox, outbox, replayDir);
    Check("spool processes valid job", worker.Drain(op => op == "probe.session" ? 0 : 7) == 1);
    var outcome = File.ReadAllText(Path.Combine(outbox, spoolJob.JobId + ".status.json"));
    Check("spool result metadata", outcome.Contains("\"completed\"", StringComparison.Ordinal));
    Check("spool never echoes data", !outcome.Contains("payload", StringComparison.Ordinal));
    Check("spool idempotent", worker.Drain(_ => 0) == 0);

    var denied = job with
    {
        JobId = "22222222222222222222222222222222",
        Operation = "shell.execute",
        IssuedAtUnix = spoolNow.ToUnixTimeSeconds() - 5,
        ExpiresAtUnix = spoolNow.ToUnixTimeSeconds() + 50,
        Signature = ""
    };
    denied = denied with { Signature = JobAdmission.SignForTest(denied, secret) };
    File.WriteAllText(Path.Combine(inbox, denied.JobId + ".json"), Json(denied));
    Check("spool denies even signed shell", worker.Drain(_ => 0) == 1);
    var deniedOutcome = File.ReadAllText(Path.Combine(outbox, denied.JobId + ".status.json"));
    Check("spool denial reason", deniedOutcome.Contains("operation_denied", StringComparison.Ordinal));
}
finally { Directory.Delete(spoolRoot, recursive: true); }

if (failures.Count != 0)
{
    foreach (var failure in failures) Console.Error.WriteLine("FAIL: " + failure);
    return 1;
}
Console.WriteLine($"PASS: {checkedCount} protocol admission, replay and tenant-isolation checks");
return 0;

sealed class MemoryGuard : IReplayGuard
{
    private readonly HashSet<string> _ids = new(StringComparer.Ordinal);
    public bool TryClaim(string jobId) => _ids.Add(jobId);
}
