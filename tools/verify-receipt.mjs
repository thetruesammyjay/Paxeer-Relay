#!/usr/bin/env node

import { readFile } from "node:fs/promises";
import { createHash, createPublicKey, verify as verifySignature } from "node:crypto";

const INTEGER_TOKEN = /^-?(?:0|[1-9]\d*)$/;
const HASH_TOKEN = /^0x[0-9a-f]{64}$/;
const SIGNATURE_TOKEN = /^0x(?:[0-9a-fA-F]{2})+$/;
const CURVE_ORDERS = {
  secp256k1: BigInt("0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141"),
  prime256v1: BigInt("0xFFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551"),
  secp256r1: BigInt("0xFFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551"),
};

function fail(message) {
  throw new Error(message);
}

function assertUnicodeScalars(value) {
  for (let index = 0; index < value.length; index += 1) {
    const code = value.charCodeAt(index);
    if (code >= 0xd800 && code <= 0xdbff) {
      const next = value.charCodeAt(index + 1);
      if (!(next >= 0xdc00 && next <= 0xdfff)) {
        fail("Canonical JSON strings must contain valid Unicode.");
      }
      index += 1;
    } else if (code >= 0xdc00 && code <= 0xdfff) {
      fail("Canonical JSON strings must contain valid Unicode.");
    }
  }
}

function parseReceiptJson(source) {
  const receipt = JSON.parse(source, (_key, value, context) => {
    if (typeof value === "number" && typeof context?.source === "string") {
      if (INTEGER_TOKEN.test(context.source)) return BigInt(context.source);
    }
    return value;
  });

  const rejectUnsafeNumbers = (value) => {
    if (typeof value === "number") {
      if (!Number.isFinite(value)) fail("Receipt contains a non-finite number.");
      if (Number.isInteger(value) && !Number.isSafeInteger(value)) {
        fail(
          "This Node.js runtime cannot preserve a large JSON integer. " +
            "Use a runtime with JSON.parse reviver context.source support.",
        );
      }
      return;
    }
    if (Array.isArray(value)) {
      for (const item of value) rejectUnsafeNumbers(item);
      return;
    }
    if (value !== null && typeof value === "object") {
      for (const item of Object.values(value)) rejectUnsafeNumbers(item);
    }
  };
  rejectUnsafeNumbers(receipt);
  return receipt;
}

function normalizeFloat(value) {
  if (!Number.isFinite(value)) fail("Non-finite floats are not valid in a receipt.");
  if (Object.is(value, -0) || value === 0) return "0";

  const source = value.toString().toLowerCase();
  const [coefficient, exponentToken] = source.split("e");
  const exponent = exponentToken === undefined ? 0 : Number(exponentToken);
  const negative = coefficient.startsWith("-");
  const unsigned = negative ? coefficient.slice(1) : coefficient;
  const dot = unsigned.indexOf(".");
  const integerDigits = dot === -1 ? unsigned.length : dot;
  const digits = unsigned.replace(".", "");
  const decimalPosition = integerDigits + exponent;

  let token;
  if (decimalPosition <= 0) {
    token = `0.${"0".repeat(-decimalPosition)}${digits}`;
  } else if (decimalPosition >= digits.length) {
    token = digits + "0".repeat(decimalPosition - digits.length);
  } else {
    token = `${digits.slice(0, decimalPosition)}.${digits.slice(decimalPosition)}`;
  }

  if (token.includes(".")) token = token.replace(/0+$/, "").replace(/\.$/, "");
  token = token.replace(/^0+(?=\d)/, "");
  if (token.startsWith(".")) token = `0${token}`;
  if (negative) token = `-${token}`;
  return token === "-0" ? "0" : token;
}

function canonicalJson(value) {
  if (value === null) return "null";
  if (value === true) return "true";
  if (value === false) return "false";
  if (typeof value === "string") {
    assertUnicodeScalars(value);
    return JSON.stringify(value);
  }
  if (typeof value === "bigint") return value.toString(10);
  if (typeof value === "number") {
    if (Number.isInteger(value) && Number.isSafeInteger(value)) return String(value);
    return normalizeFloat(value);
  }
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
  if (typeof value === "object") {
    const keys = Object.keys(value).sort();
    for (const key of keys) assertUnicodeScalars(key);
    return `{${keys
      .map((key) => `${JSON.stringify(key)}:${canonicalJson(value[key])}`)
      .join(",")}}`;
  }
  return fail(`Unsupported JSON value: ${typeof value}.`);
}

function canonicalTimestamp(value, fieldName) {
  if (typeof value !== "string") fail(`Receipt field ${fieldName} must be a timestamp string.`);
  const match = value.match(
    /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,6}))?(Z|[+-]\d{2}:\d{2})?$/,
  );
  if (!match) fail(`Receipt field ${fieldName} is not a supported ISO-8601 timestamp.`);

  const [, yearText, monthText, dayText, hourText, minuteText, secondText, fractionText = "", zone = "Z"] = match;
  const year = Number(yearText);
  const month = Number(monthText);
  const day = Number(dayText);
  const hour = Number(hourText);
  const minute = Number(minuteText);
  const second = Number(secondText);
  const fraction = fractionText.padEnd(6, "0");
  if (year < 1 || month < 1 || month > 12 || hour > 23 || minute > 59 || second > 59) {
    fail(`Receipt field ${fieldName} has an invalid date or time.`);
  }

  const local = new Date(0);
  local.setUTCFullYear(year, month - 1, day);
  local.setUTCHours(hour, minute, second, 0);
  if (
    local.getUTCFullYear() !== year ||
    local.getUTCMonth() !== month - 1 ||
    local.getUTCDate() !== day
  ) {
    fail(`Receipt field ${fieldName} has an invalid calendar date.`);
  }

  let offsetMinutes = 0;
  if (zone !== "Z") {
    const sign = zone[0] === "+" ? 1 : -1;
    const zoneHour = Number(zone.slice(1, 3));
    const zoneMinute = Number(zone.slice(4, 6));
    if (zoneHour > 23 || zoneMinute > 59) {
      fail(`Receipt field ${fieldName} has an invalid UTC offset.`);
    }
    offsetMinutes = sign * (zoneHour * 60 + zoneMinute);
  }

  const utc = new Date(local.getTime() - offsetMinutes * 60_000);
  const iso = utc.toISOString();
  if (!/^\d{4}-/.test(iso)) fail(`Receipt field ${fieldName} is outside the supported date range.`);
  return `${iso.slice(0, 19)}.${fraction}Z`;
}

function canonicalReceipt(receipt) {
  if (receipt === null || typeof receipt !== "object" || Array.isArray(receipt)) {
    fail("Receipt JSON must be an object.");
  }
  const normalized = { ...receipt };
  for (const field of ["signature", "receipt_hash", "signing_key_id"]) delete normalized[field];

  if (Object.hasOwn(normalized, "issued_at")) {
    normalized.issued_at = canonicalTimestamp(normalized.issued_at, "issued_at");
  }
  if (normalized.execution !== null && typeof normalized.execution === "object") {
    normalized.execution = { ...normalized.execution };
    for (const field of ["started_at", "completed_at"]) {
      if (Object.hasOwn(normalized.execution, field)) {
        normalized.execution[field] = canonicalTimestamp(
          normalized.execution[field],
          `execution.${field}`,
        );
      }
    }
  }
  return Buffer.from(canonicalJson(normalized), "utf8");
}

function derLength(signature, state) {
  if (state.offset >= signature.length) fail("Invalid DER signature length.");
  const first = signature[state.offset++];
  if (first < 0x80) return first;
  const count = first & 0x7f;
  if (count === 0 || count > 4 || state.offset + count > signature.length) {
    fail("Invalid DER signature length.");
  }
  if (signature[state.offset] === 0) fail("Non-canonical DER signature length.");
  let length = 0;
  for (let index = 0; index < count; index += 1) {
    length = length * 256 + signature[state.offset++];
  }
  if (length < 0x80) fail("Non-canonical DER signature length.");
  return length;
}

function derInteger(signature, state) {
  if (signature[state.offset++] !== 0x02) fail("Invalid DER ECDSA integer.");
  const length = derLength(signature, state);
  const end = state.offset + length;
  if (length === 0 || end > signature.length) fail("Invalid DER ECDSA integer.");
  const bytes = signature.subarray(state.offset, end);
  state.offset = end;
  if (bytes[0] & 0x80) fail("Negative DER ECDSA integer.");
  if (bytes.length > 1 && bytes[0] === 0 && (bytes[1] & 0x80) === 0) {
    fail("Non-canonical DER ECDSA integer.");
  }
  return BigInt(`0x${bytes.toString("hex")}`);
}

function assertLowSDer(signature, order) {
  const state = { offset: 0 };
  if (signature[state.offset++] !== 0x30) fail("Invalid DER ECDSA signature.");
  const sequenceLength = derLength(signature, state);
  if (sequenceLength !== signature.length - state.offset) fail("Invalid DER ECDSA signature.");
  const r = derInteger(signature, state);
  const s = derInteger(signature, state);
  if (state.offset !== signature.length) fail("Invalid DER ECDSA signature.");
  if (r <= 0n || r >= order || s <= 0n || s > order / 2n) {
    fail("ECDSA signature is out of range or not low-S.");
  }
}

function verifyReceipt(receipt, publicKeyPem) {
  if (typeof receipt.receipt_hash !== "string" || !HASH_TOKEN.test(receipt.receipt_hash)) {
    fail("Receipt is missing a valid receipt_hash.");
  }
  if (typeof receipt.signature !== "string" || !SIGNATURE_TOKEN.test(receipt.signature)) {
    fail("Receipt is missing a valid 0x-prefixed signature.");
  }

  const canonical = canonicalReceipt(receipt);
  const calculatedHash = `0x${createHash("sha256").update(canonical).digest("hex")}`;
  if (calculatedHash !== receipt.receipt_hash) fail("Receipt hash does not match canonical contents.");

  const publicKey = createPublicKey(publicKeyPem);
  if (publicKey.asymmetricKeyType !== "ec") fail("Trusted key must be an EC public key.");
  const curveName = publicKey.asymmetricKeyDetails?.namedCurve;
  const order = CURVE_ORDERS[curveName];
  if (!order) fail(`Unsupported ECDSA curve: ${curveName ?? "unknown"}.`);

  const signature = Buffer.from(receipt.signature.slice(2), "hex");
  assertLowSDer(signature, order);
  if (!verifySignature("sha256", canonical, publicKey, signature)) {
    fail("ECDSA signature verification failed.");
  }

  return {
    valid: true,
    receipt_hash: calculatedHash,
    signing_key_id: receipt.signing_key_id ?? null,
    canonical_bytes: canonical.toString("utf8"),
  };
}

async function main() {
  const [, , receiptPath, publicKeyPath] = process.argv;
  if (!receiptPath || !publicKeyPath) {
    fail("Usage: node tools/verify-receipt.mjs <receipt.json> <trusted-public-key.pem>");
  }
  const [receiptText, publicKeyPem] = await Promise.all([
    readFile(receiptPath, "utf8"),
    readFile(publicKeyPath, "utf8"),
  ]);
  const result = verifyReceipt(parseReceiptJson(receiptText), publicKeyPem);
  process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
}

main().catch((error) => {
  process.stderr.write(`Receipt verification failed: ${error.message}\n`);
  process.exitCode = 1;
});
