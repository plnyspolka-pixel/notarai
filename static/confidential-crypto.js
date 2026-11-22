/* Client-side encryption for the optional NotarAI confidential workflow.
 * Neither the DEK nor plaintext is sent to the application server.
 * Public key SHA-256 MUST be independently pinned by the client.
 */
const ID = /^[A-Za-z0-9_-]{1,80}$/;
const KMS = /^arn:aws:kms:eu-[a-z0-9-]+:\d{12}:key\/[A-Za-z0-9-]+$/;
const MAX_BYTES = 25 * 1024 * 1024;
const DOCUMENT_VERSION = /^[a-f0-9]{32}$/;

function toBase64(bytes) {
  let binary = "";
  const step = 8192;
  for (let i = 0; i < bytes.length; i += step) {
    binary += String.fromCharCode(...bytes.subarray(i, i + step));
  }
  return btoa(binary);
}

function fromBase64(value) {
  const binary = atob(value);
  return Uint8Array.from(binary, (ch) => ch.charCodeAt(0));
}

function assertId(value) {
  if (typeof value !== "string" || !ID.test(value)) {
    throw new Error("Invalid document identifier");
  }
}

function pemToDer(pem) {
  if (typeof pem !== "string" || !pem.includes("BEGIN PUBLIC KEY")) {
    throw new Error("Expected KMS public key PEM");
  }
  const encoded = pem.replace(/-----BEGIN PUBLIC KEY-----|-----END PUBLIC KEY-----|\s/g, "");
  return fromBase64(encoded);
}

export async function sha256PublicKey(pem) {
  const der = pemToDer(pem);
  const digest = await crypto.subtle.digest("SHA-256", der);
  return toBase64(new Uint8Array(digest));
}

export async function encryptForConfidentialTask({
  bytes, tenantId, caseId, objectId, documentVersion,
  kmsKeyArn, publicKeyPem, pinnedKeySha256,
}) {
  [tenantId, caseId, objectId].forEach(assertId);
  if (typeof kmsKeyArn !== "string" || !KMS.test(kmsKeyArn)) {
    throw new Error("Expected regional AWS KMS key ARN");
  }
  if (!(bytes instanceof ArrayBuffer) && !ArrayBuffer.isView(bytes)) {
    throw new Error("Expected binary document");
  }
  const source = bytes instanceof ArrayBuffer
    ? new Uint8Array(bytes)
    : new Uint8Array(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  if (source.byteLength === 0 || source.byteLength > MAX_BYTES) {
    throw new Error("Unsupported document size");
  }
  if (typeof pinnedKeySha256 !== "string" || !pinnedKeySha256) {
    throw new Error("Independent KMS key fingerprint is required");
  }
  const der = pemToDer(publicKeyPem);
  const digest = await sha256PublicKey(publicKeyPem);
  if (digest !== pinnedKeySha256) {
    throw new Error("KMS public key fingerprint mismatch");
  }
  const publicKey = await crypto.subtle.importKey(
    "spki", der, { name: "RSA-OAEP", hash: "SHA-256" }, false, ["encrypt"]
  );
  const logicalVersion = documentVersion === undefined
    ? Array.from(crypto.getRandomValues(new Uint8Array(16)), x => x.toString(16).padStart(2, "0")).join("")
    : documentVersion;
  if (typeof logicalVersion !== "string" || !DOCUMENT_VERSION.test(logicalVersion)) {
    throw new Error("Invalid logical document version");
  }
  const dekBytes = crypto.getRandomValues(new Uint8Array(32));
  const nonce = crypto.getRandomValues(new Uint8Array(12));
  const associatedData = new TextEncoder().encode(
    ["notarai-v2", tenantId, caseId, objectId, logicalVersion, kmsKeyArn, digest].join("|")
  );
  try {
    const aesKey = await crypto.subtle.importKey(
      "raw", dekBytes, { name: "AES-GCM" }, false, ["encrypt"]
    );
    const [encrypted, wrapped] = await Promise.all([
      crypto.subtle.encrypt(
        { name: "AES-GCM", iv: nonce, additionalData: associatedData, tagLength: 128 },
        aesKey, source
      ),
      crypto.subtle.encrypt({ name: "RSA-OAEP" }, publicKey, dekBytes),
    ]);
    return {
      version: 2,
      document_version: logicalVersion,
      public_key_sha256: digest,
      algorithm: "AES-256-GCM+RSA-OAEP-SHA256",
      tenant_id: tenantId,
      case_id: caseId,
      object_id: objectId,
      kms_key_arn: kmsKeyArn,
      nonce: toBase64(nonce),
      wrapped_dek: toBase64(new Uint8Array(wrapped)),
      ciphertext: toBase64(new Uint8Array(encrypted)),
    };
  } finally {
    dekBytes.fill(0);
  }
}
