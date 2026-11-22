/* Operator-hosted courier accepts ONLY ciphertext envelopes.
 * Original plaintext is prepared by an independently released offline client.
 * This view never loads or asks for original documents; it cannot submit forms.
 */
"use strict";
const button = document.getElementById("store");
const preview = document.getElementById("preview");
const receiptButton = document.getElementById("receipt-store");
const receiptInput = document.getElementById("receipt-file");
const selected = document.getElementById("encrypted");
const status = document.getElementById("status");
const ID = /^[A-Za-z0-9_-]{1,80}$/;
const envelopeFields = new Set([
  "version", "algorithm", "tenant_id", "case_id", "object_id",
  "kms_key_arn", "document_version", "public_key_sha256",
  "nonce", "wrapped_dek", "ciphertext",
]);
let previewTarget = null;
let pendingOrigin = null;

button.addEventListener("click", async () => {
  button.disabled = true;
  preview.disabled = true;
  receiptButton.disabled = true;
  pendingOrigin = null;
  previewTarget = null;
  status.textContent = "";
  try {
    const file = selected.files[0];
    if (!file || !file.name.endsWith(".encrypted.json") ||
        file.size > 35 * 1024 * 1024 || file.size === 0) {
      throw new Error("invalid encrypted file");
    }
    const text = await file.text();
    const payload = JSON.parse(text);
    if (payload === null || typeof payload !== "object" ||
        Array.isArray(payload) || Object.keys(payload).length !== envelopeFields.size ||
        !Object.keys(payload).every((key) => envelopeFields.has(key)) ||
        payload.version !== 2 ||
        payload.algorithm !== "AES-256-GCM+RSA-OAEP-SHA256" ||
        !ID.test(payload.tenant_id) || !ID.test(payload.case_id) ||
        !ID.test(payload.object_id) ||
        !/^[a-f0-9]{32}$/.test(payload.document_version) ||
        !/^[A-Za-z0-9+/]{43}=$/.test(payload.public_key_sha256) ||
        !/^arn:aws:kms:eu-central-1:[0-9]{12}:key\/[A-Za-z0-9-]+$/.test(payload.kms_key_arn) ||
        ![payload.nonce, payload.wrapped_dek, payload.ciphertext].every(
          (v) => typeof v === "string" && v.length > 0
        )) {
      throw new Error("not an approved ciphertext envelope");
    }
    const path = "/api/confidential/envelopes/" +
                 encodeURIComponent(payload.case_id) + "/" +
                 encodeURIComponent(payload.object_id);
    const result = await fetch(path, {
      method: "PUT", credentials: "same-origin",
      headers: {"Content-Type": "application/json"}, body: text,
    });
    if (!result.ok) throw new Error("server rejected encrypted upload");
    const response = await result.json();
    if (response.stored !== true || !response.s3_version ||
        !/^[a-f0-9]{64}$/.test(response.ciphertext_sha256) ||
        response.document_version !== payload.document_version) {
      throw new Error("unconfirmed encrypted object digest/version");
    }
    pendingOrigin = {
      tenantId: payload.tenant_id, caseId: payload.case_id,
      objectId: payload.object_id, documentVersion: payload.document_version,
      s3Version: response.s3_version, ciphertextSha256: response.ciphertext_sha256,
      kmsArn: payload.kms_key_arn, keyPin: payload.public_key_sha256,
    };
    receiptButton.disabled = false;
    status.textContent = "Ciphertext zapisany. Weryfikuj SHA-256 " +
      response.ciphertext_sha256 + " i wersję S3 " + response.s3_version +
      " niezależnie, następnie dołącz podpisane potwierdzenie. Podgląd zablokowany do tej chwili.";
  } catch (_) {
    status.textContent = "Odmowa importu: wybierz prawidłowy plik .encrypted.json i zweryfikuj uprawnienia.";
  } finally {
    selected.value = "";
    button.disabled = false;
  }
});

receiptButton.addEventListener("click", async () => {
  receiptButton.disabled = true;
  preview.disabled = true;
  previewTarget = null;
  try {
    const file = receiptInput.files[0];
    if (!pendingOrigin || !file || !file.name.endsWith(".origin.json") ||
        file.size === 0 || file.size > 8192) {
      throw new Error("wrong signed origin receipt file");
    }
    const text = await file.text();
    const bundle = JSON.parse(text);
    const receipt = bundle?.receipt;
    if (bundle?.schema !== "notarai.signed-origin-receipt.v1" ||
        typeof bundle.signature_b64 !== "string" ||
        !/^[A-Za-z0-9+/]{86}==$/.test(bundle.signature_b64) ||
        !receipt || typeof receipt !== "object" ||
        receipt.schema !== "notarai.document-origin.v1" ||
        receipt.tenant_id !== pendingOrigin.tenantId ||
        receipt.case_id !== pendingOrigin.caseId ||
        receipt.object_id !== pendingOrigin.objectId ||
        receipt.document_version !== pendingOrigin.documentVersion ||
        receipt.s3_version !== pendingOrigin.s3Version ||
        receipt.ciphertext_sha256 !== pendingOrigin.ciphertextSha256 ||
        receipt.kms_key_arn !== pendingOrigin.kmsArn ||
        receipt.key_pin !== pendingOrigin.keyPin) {
      throw new Error("origin receipt does not bind exact ciphertext");
    }
    const path = "/api/confidential/origin-receipts/" +
      encodeURIComponent(pendingOrigin.caseId) + "/" +
      encodeURIComponent(pendingOrigin.objectId);
    const result = await fetch(path, {
      method: "PUT", credentials: "same-origin",
      headers: {"Content-Type": "application/json"}, body: text,
    });
    if (!result.ok) throw new Error("receipt rejected");
    const response = await result.json();
    if (response.stored !== true || response.signature_verified !== false) {
      throw new Error("untrusted receipt status");
    }
    previewTarget = [pendingOrigin.caseId, pendingOrigin.objectId];
    status.textContent = "Potwierdzenie zapisane. Podpis zweryfikuje Nitro przed odszyfrowaniem.";
    preview.disabled = false;
  } catch (_) {
    status.textContent = "Brak poprawnego potwierdzenia. Podgląd pozostaje zablokowany.";
    receiptButton.disabled = false;
  } finally {
    receiptInput.value = "";
  }
});

preview.addEventListener("click", async () => {
  if (!previewTarget) return;
  preview.disabled = true;
  status.textContent = "Przygotowanie podglądu bez wysyłania formularza…";
  try {
    const [caseId, objectId] = previewTarget;
    const result = await fetch(
      "/api/confidential/preview/" + encodeURIComponent(caseId) +
      "/" + encodeURIComponent(objectId),
      {method: "POST", credentials: "same-origin", body: null}
    );
    if (!result.ok) throw new Error("queue denied");
    const response = await result.json();
    if (response.operation !== "preview-only" || response.can_submit !== false) {
      throw new Error("unsafe preview response");
    }
    status.textContent = "Podgląd zlecony. Formularz nie zostanie wysłany.";
  } catch (_) {
    status.textContent = "Nie można zlecić podglądu. Sprawdź rejestr zadania.";
  }
});
