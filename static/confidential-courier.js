/* Operator-hosted courier accepts ONLY ciphertext envelopes.
 * Original plaintext is prepared by an independently released offline client.
 * This view never loads or asks for original documents; it cannot submit forms.
 */
"use strict";
const button = document.getElementById("store");
const preview = document.getElementById("preview");
const selected = document.getElementById("encrypted");
const status = document.getElementById("status");
const ID = /^[A-Za-z0-9_-]{1,80}$/;
const envelopeFields = new Set([
  "version", "algorithm", "tenant_id", "case_id", "object_id",
  "kms_key_arn", "document_version", "public_key_sha256",
  "nonce", "wrapped_dek", "ciphertext",
]);
let previewTarget = null;

button.addEventListener("click", async () => {
  button.disabled = true;
  preview.disabled = true;
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
    if (response.stored !== true || !response.s3_version) {
      throw new Error("unconfirmed document version");
    }
    previewTarget = [payload.case_id, payload.object_id];
    preview.disabled = false;
    status.textContent = "Potwierdzono zapis zaszyfrowanego obiektu. Podgląd jest opcjonalny.";
  } catch (_) {
    status.textContent = "Odmowa importu: wybierz prawidłowy plik .encrypted.json i zweryfikuj uprawnienia.";
  } finally {
    selected.value = "";
    button.disabled = false;
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
