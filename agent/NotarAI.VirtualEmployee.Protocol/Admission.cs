using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace NotarAI.VirtualEmployee.Protocol;

/// <summary>
/// Protocol v1 only permits harmless, read-only diagnostics. There is no
/// generic command, path, script, screenshot or UI text in a signed job.
/// </summary>
public sealed record SignedJob(
    int Schema,
    string TenantId,
    string JobId,
    string Operation,
    long IssuedAtUnix,
    long ExpiresAtUnix,
    string Nonce,
    string Signature
);

public interface IReplayGuard
{
    bool TryClaim(string jobId);
}

public sealed class FileReplayGuard : IReplayGuard
{
    private readonly string _directory;

    public FileReplayGuard(string directory)
    {
        _directory = Path.GetFullPath(directory);
        if (!Directory.Exists(_directory))
            throw new DirectoryNotFoundException("Pre-provision the private replay directory");
        if ((File.GetAttributes(_directory) & FileAttributes.ReparsePoint) != 0)
            throw new InvalidOperationException("Replay directory cannot be a reparse point");
    }

    public bool TryClaim(string jobId)
    {
        if (!Regex.IsMatch(jobId, @"\A[a-f0-9]{32}\z", RegexOptions.CultureInvariant))
            return false;
        var file = Path.Combine(_directory, jobId + ".claimed");
        try
        {
            using var marker = new FileStream(file, FileMode.CreateNew, FileAccess.Write, FileShare.None);
            marker.Flush(flushToDisk: true);
            return true;
        }
        catch (IOException) when (File.Exists(file))
        {
            return false; // Replay detected across process restarts.
        }
    }
}

public sealed record AdmissionResult(bool Allowed, string Code, string? Operation = null)
{
    public static AdmissionResult Reject(string code) => new(false, code);
    public static AdmissionResult Permit(string operation) => new(true, "accepted", operation);
}

public static class JobAdmission
{
    private static readonly Regex Tenant = new(@"\A[a-z][a-z0-9]{2,11}\z", RegexOptions.Compiled | RegexOptions.CultureInvariant);
    private static readonly Regex Hex32 = new(@"\A[a-f0-9]{32}\z", RegexOptions.Compiled | RegexOptions.CultureInvariant);
    private static readonly Regex Hex64 = new(@"\A[a-f0-9]{64}\z", RegexOptions.Compiled | RegexOptions.CultureInvariant);
    private static readonly HashSet<string> Keys = new(StringComparer.Ordinal)
    {
        "schema", "tenantId", "jobId", "operation", "issuedAtUnix",
        "expiresAtUnix", "nonce", "signature"
    };
    private static readonly HashSet<string> AllowedOperations = new(StringComparer.Ordinal)
    {
        "probe.session", "probe.notepad"
    };

    /// <summary>Exact field names and types, no unknown or duplicate properties.</summary>
    public static SignedJob ParseStrict(string json)
    {
        if (Encoding.UTF8.GetByteCount(json) > 4096)
            throw new FormatException("Job exceeds size limit");
        using var doc = JsonDocument.Parse(json, new JsonDocumentOptions
        {
            AllowTrailingCommas = false,
            CommentHandling = JsonCommentHandling.Disallow,
            MaxDepth = 2
        });
        if (doc.RootElement.ValueKind != JsonValueKind.Object)
            throw new FormatException("Expected an object");
        var seen = new HashSet<string>(StringComparer.Ordinal);
        foreach (var field in doc.RootElement.EnumerateObject())
        {
            if (!Keys.Contains(field.Name) || !seen.Add(field.Name))
                throw new FormatException("Unknown or duplicate field");
        }
        if (seen.Count != Keys.Count)
            throw new FormatException("Missing field");
        var item = doc.RootElement;
        return new SignedJob(
            item.GetProperty("schema").GetInt32(),
            item.GetProperty("tenantId").GetString() ?? "",
            item.GetProperty("jobId").GetString() ?? "",
            item.GetProperty("operation").GetString() ?? "",
            item.GetProperty("issuedAtUnix").GetInt64(),
            item.GetProperty("expiresAtUnix").GetInt64(),
            item.GetProperty("nonce").GetString() ?? "",
            item.GetProperty("signature").GetString() ?? ""
        );
    }

    public static string Canonical(SignedJob job) => string.Join("\n",
        "notarai-ve/v1", job.Schema.ToString(CultureInfo.InvariantCulture),
        job.TenantId, job.JobId, job.Operation,
        job.IssuedAtUnix.ToString(CultureInfo.InvariantCulture),
        job.ExpiresAtUnix.ToString(CultureInfo.InvariantCulture), job.Nonce);

    public static string SignForTest(SignedJob job, byte[] secret)
    {
        if (secret.Length < 32) throw new ArgumentException("HMAC key must be at least 32 bytes");
        return Convert.ToHexString(HMACSHA256.HashData(secret, Encoding.UTF8.GetBytes(Canonical(job)))).ToLowerInvariant();
    }

    public static AdmissionResult Admit(
        string json, string expectedTenant, ReadOnlySpan<byte> secret,
        DateTimeOffset now, IReplayGuard replay)
    {
        SignedJob job;
        try { job = ParseStrict(json); }
        catch (Exception e) when (e is JsonException or InvalidOperationException or FormatException or OverflowException)
        {
            return AdmissionResult.Reject("malformed");
        }
        if (secret.Length < 32 || !Tenant.IsMatch(expectedTenant))
            return AdmissionResult.Reject("invalid_configuration");
        if (job.Schema != 1 || !Tenant.IsMatch(job.TenantId) ||
            !Hex32.IsMatch(job.JobId) || !Hex32.IsMatch(job.Nonce) ||
            !Hex64.IsMatch(job.Signature))
            return AdmissionResult.Reject("invalid_schema");
        if (!string.Equals(job.TenantId, expectedTenant, StringComparison.Ordinal))
            return AdmissionResult.Reject("tenant_mismatch");
        if (!AllowedOperations.Contains(job.Operation))
            return AdmissionResult.Reject("operation_denied");
        var nowUnix = now.ToUnixTimeSeconds();
        // Bound issued time first, before adding/subtracting timestamps.
        // This prevents signed malformed long.MinValue/long.MaxValue overflow.
        if (job.IssuedAtUnix < nowUnix - 300 ||
            job.IssuedAtUnix > nowUnix + 60 ||
            job.ExpiresAtUnix <= nowUnix ||
            job.ExpiresAtUnix <= job.IssuedAtUnix ||
            job.ExpiresAtUnix > job.IssuedAtUnix + 300)
            return AdmissionResult.Reject("expired_or_invalid_time");

        var expected = HMACSHA256.HashData(secret, Encoding.UTF8.GetBytes(Canonical(job)));
        // Verify with a constant-time comparison and reject malformed hex signatures.
        var provided = Convert.FromHexString(job.Signature);
        if (!CryptographicOperations.FixedTimeEquals(expected, provided))
            return AdmissionResult.Reject("bad_signature");
        // Claim only after every validation; the replay journal must be durable
        // before a future side-effecting adapter may ever run.
        if (!replay.TryClaim(job.JobId))
            return AdmissionResult.Reject("duplicate");
        return AdmissionResult.Permit(job.Operation);
    }
}
