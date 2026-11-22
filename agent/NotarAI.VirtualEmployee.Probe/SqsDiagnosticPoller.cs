using System.Security.Cryptography;
using System.Text;
using Amazon.SQS;
using Amazon.SQS.Model;
using NotarAI.VirtualEmployee.Protocol;

namespace NotarAI.VirtualEmployee.Probe;

/// <summary>
/// Private SQS transport for synthetic diagnostics only. The queue only transports
/// schema-v1 envelopes; it cannot carry UI text, arbitrary scripts or documents.
/// No AWS static access keys: use the EC2 role's default credential chain.
/// </summary>
internal sealed class SqsDiagnosticPoller
{
    private readonly IAmazonSQS _client;
    private readonly string _queueUrl;
    private readonly string _tenant;
    private readonly ReadOnlyMemory<byte> _key;
    private readonly FileReplayGuard _replay;
    private readonly string _outbox;

    public SqsDiagnosticPoller(IAmazonSQS client, string queueUrl, string tenant,
        byte[] key, string replayDirectory, string outbox)
    {
        if (!ValidQueueUrl(queueUrl, tenant))
            throw new ArgumentException("Queue URL is not the isolated Frankfurt tenant pilot queue");
        if (key.Length < 32)
            throw new ArgumentException("Invalid synthetic signing key");
        if (!Directory.Exists(outbox))
            throw new DirectoryNotFoundException("Provision the private metadata-only outbox");
        _outbox = Path.GetFullPath(outbox);
        if ((File.GetAttributes(_outbox) & FileAttributes.ReparsePoint) != 0)
            throw new InvalidOperationException("Outbox cannot be a reparse point");
        _replay = new FileReplayGuard(replayDirectory);
        _client = client;
        _queueUrl = queueUrl;
        _tenant = tenant;
        _key = key;
    }

    internal static bool ValidQueueUrl(string? queueUrl, string tenant)
    {
        if (string.IsNullOrWhiteSpace(queueUrl) ||
            !Uri.TryCreate(queueUrl, UriKind.Absolute, out var uri))
            return false;
        if (uri.Scheme != Uri.UriSchemeHttps ||
            !string.Equals(uri.Host, "sqs.eu-central-1.amazonaws.com", StringComparison.Ordinal) ||
            !uri.IsDefaultPort || !string.IsNullOrEmpty(uri.Query) ||
            !string.IsNullOrEmpty(uri.Fragment) || !string.IsNullOrEmpty(uri.UserInfo))
            return false;
        if (!System.Text.RegularExpressions.Regex.IsMatch(tenant, @"\A[a-z][a-z0-9]{2,11}\z"))
            return false;
        var segments = uri.AbsolutePath.Split('/', StringSplitOptions.RemoveEmptyEntries);
        return segments.Length == 2 &&
            System.Text.RegularExpressions.Regex.IsMatch(segments[0], @"\A[0-9]{12}\z") &&
            string.Equals(segments[1], $"notarai-ve-{tenant}-jobs.fifo", StringComparison.Ordinal);
    }

    public async Task<int> PollOnceAsync(Func<string, int> execute, CancellationToken cancellation)
    {
        // One message in flight, bounded long-polling. No body or receipt printed.
        var response = await _client.ReceiveMessageAsync(new ReceiveMessageRequest
        {
            QueueUrl = _queueUrl,
            MaxNumberOfMessages = 1,
            WaitTimeSeconds = 5,
            VisibilityTimeout = 60
        }, cancellation);
        var message = response.Messages?.FirstOrDefault();
        if (message is null)
            return 0;
        if (string.IsNullOrWhiteSpace(message.ReceiptHandle))
            throw new InvalidOperationException("Missing SQS receipt; cannot acknowledge safely");

        var body = message.Body ?? "";
        SignedJob? parsed = null;
        if (Encoding.UTF8.GetByteCount(body) <= 4096)
        {
            try { parsed = JobAdmission.ParseStrict(body); }
            catch (Exception ex) when (ex is System.Text.Json.JsonException or
                InvalidOperationException or FormatException or OverflowException) { }
        }
        // Do not trust data fields before verifying the signature: use either the
        // syntactically safe ID or an opaque digest for the status filename.
        var safeId = parsed is not null &&
            System.Text.RegularExpressions.Regex.IsMatch(parsed.JobId, @"\A[a-f0-9]{32}\z")
                ? parsed.JobId
                : Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(message.MessageId ?? "")))
                    .ToLowerInvariant()[..32];
        var outcome = Path.Combine(_outbox, safeId + ".status.json");

        // If an earlier invocation already committed a result, ack the
        // duplicate instead of executing again.
        if (!File.Exists(outcome))
        {
            string status;
            string code;
            if (parsed is null)
            {
                status = "rejected";
                code = "malformed";
            }
            else
            {
                var admission = JobAdmission.Admit(body, _tenant, _key.Span, DateTimeOffset.UtcNow, _replay);
                status = admission.Allowed ? "accepted" : "rejected";
                code = admission.Code;
                if (admission.Allowed)
                {
                    int exitCode;
                    try { exitCode = execute(admission.Operation!); }
                    catch (Exception) { exitCode = 5; }
                    status = exitCode == 0 ? "completed" : "failed";
                    code = exitCode == 0 ? "probe_success" : "probe_failed";
                }
            }
            // The result is persisted BEFORE SQS deletion. A failed write
            // leaves the message unacknowledged and eligible for redelivery.
            LocalInboxProcessor.WriteOutcome(outcome, safeId, status, code);
        }
        await _client.DeleteMessageAsync(new DeleteMessageRequest
        {
            QueueUrl = _queueUrl,
            ReceiptHandle = message.ReceiptHandle
        }, cancellation);
        return 1;
    }
}
