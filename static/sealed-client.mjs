/**
 * NotarAI Sealed prototype (v1). Run from a pinned, locally installed copy
 * for operator-blind assurance; a server-served script can be replaced.
 * No plaintext, passphrase or AES key is sent to the NotarAI API.
 */
const te = new TextEncoder();
const td = new TextDecoder("utf-8", { fatal: true });
const SCHEMA = "notarai.sealed.v1";
const ROUNDS = 600_000;
const MAX_BYTES = 4 * 1024 * 1024;
const B64URL = /^[A-Za-z0-9_-]+$/;
const HEX_ID = /^[a-f0-9-]{36}$/i;

function bytesToB64Url(bytes) {
  let binary = "";
  for (const value of bytes) binary += String.fromCharCode(value);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}
function b64UrlToBytes(value) {
  if (typeof value !== "string" || !B64URL.test(value)) throw new Error("Invalid base64url");
  const padded = value.replace(/-/g, "+").replace(/_/g, "/").padEnd(Math.ceil(value.length / 4) * 4, "=");
  return Uint8Array.from(atob(padded), c => c.charCodeAt(0));
}
function validText(value, name, max) {
  if (typeof value !== "string" || !value || value.length > max ||
      /[\u0000-\u001f\u007f]/.test(value)) throw new Error("Invalid " + name);
  return value;
}
export function associatedData(documentId, tenantRef) {
  validText(documentId, "documentId", 64);
  validText(tenantRef, "tenantRef", 120);
  if (!HEX_ID.test(documentId)) throw new Error("documentId must be UUID");
  return te.encode(SCHEMA + "\u0000" + tenantRef + "\u0000" + documentId);
}
async function keyFor(passphrase, salt, rounds) {
  if (typeof passphrase !== "string" || passphrase.length < 16 || passphrase.length > 1024)
    throw new Error("Use a passphrase of at least 16 characters");
  const seed = await crypto.subtle.importKey("raw", te.encode(passphrase), "PBKDF2", false, ["deriveKey"]);
  return await crypto.subtle.deriveKey(
    { name: "PBKDF2", salt, iterations: rounds, hash: "SHA-256" },
    seed, { name: "AES-GCM", length: 256 }, false, ["encrypt", "decrypt"]
  );
}
/** Returns ciphertext-only JSON suitable for upload. */
export async function sealBytes(plaintext, passphrase, tenantRef, documentId = crypto.randomUUID()) {
  if (!(plaintext instanceof Uint8Array) || plaintext.length < 1 || plaintext.length > MAX_BYTES)
    throw new Error("Document size outside Sealed POC limit (1 byte - 4 MiB)");
  const salt = crypto.getRandomValues(new Uint8Array(16));
  const nonce = crypto.getRandomValues(new Uint8Array(12));
  const associated = associatedData(documentId, tenantRef);
  const key = await keyFor(passphrase, salt, ROUNDS);
  const ciphertext = new Uint8Array(await crypto.subtle.encrypt(
    { name: "AES-GCM", iv: nonce, additionalData: associated, tagLength: 128 },
    key, plaintext
  ));
  return {
    schema: SCHEMA, documentId, tenantRef, algorithm: "AES-256-GCM",
    kdf: "PBKDF2-SHA256", iterations: ROUNDS,
    salt: bytesToB64Url(salt), nonce: bytesToB64Url(nonce),
    ciphertext: bytesToB64Url(ciphertext)
  };
}
/** Decryption happens ONLY on the user's device; the API never receives passphrase. */
export async function openSealedBytes(envelope, passphrase) {
  if (!envelope || envelope.schema !== SCHEMA || envelope.algorithm !== "AES-256-GCM" ||
      envelope.kdf !== "PBKDF2-SHA256" || envelope.iterations !== ROUNDS)
    throw new Error("Unsupported Sealed envelope");
  const salt = b64UrlToBytes(envelope.salt);
  const nonce = b64UrlToBytes(envelope.nonce);
  const ciphertext = b64UrlToBytes(envelope.ciphertext);
  if (salt.length !== 16 || nonce.length !== 12 || ciphertext.length < 17 ||
      ciphertext.length > MAX_BYTES + 16) throw new Error("Invalid Sealed envelope");
  const associated = associatedData(envelope.documentId, envelope.tenantRef);
  const key = await keyFor(passphrase, salt, ROUNDS);
  return new Uint8Array(await crypto.subtle.decrypt(
    { name: "AES-GCM", iv: nonce, additionalData: associated, tagLength: 128 },
    key, ciphertext
  ));
}
export function decodeText(bytes) { return td.decode(bytes); }
export const SEALED_SCHEMA = SCHEMA;
