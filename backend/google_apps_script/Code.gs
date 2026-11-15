const SECRET_PROPERTY_NAME = "GAS_EMAIL_RELAY_SECRET";
const MAX_RECIPIENTS = 50;
const MAX_SUBJECT_LENGTH = 250;
const MAX_BODY_BYTES = 100000;
const EMAIL_ADDRESS_PATTERN = /^[A-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?(?:\.[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?)+$/i;


function authorizeMailApp() {
  MailApp.getRemainingDailyQuota();
}


function doPost(event) {
  var payload;
  try {
    var requestBody = event && event.postData ? event.postData.contents : "";
    if (typeof requestBody !== "string" || requestBody.length > 250000) {
      return jsonResponse({ ok: false, error: "invalid_request" });
    }
    payload = JSON.parse(requestBody);
  } catch (error) {
    return jsonResponse({ ok: false, error: "invalid_request" });
  }

  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    return jsonResponse({ ok: false, error: "invalid_request" });
  }

  var expectedSecret = PropertiesService.getScriptProperties()
    .getProperty(SECRET_PROPERTY_NAME);
  if (!expectedSecret || expectedSecret.length < 32 ||
      !constantTimeEquals(payload.secret, expectedSecret)) {
    return jsonResponse({ ok: false, error: "unauthorized" });
  }

  var validationError = validatePayload(payload);
  if (validationError) {
    return jsonResponse({ ok: false, error: validationError });
  }

  var plainText = payload.text || htmlToPlainText(payload.html || "");
  var options = { name: "ReSight" };
  if (payload.html) {
    options.htmlBody = payload.html;
  }

  try {
    if (MailApp.getRemainingDailyQuota() < payload.to.length) {
      return jsonResponse({ ok: false, error: "quota_exceeded" });
    }
    MailApp.sendEmail(
      payload.to.join(","),
      payload.subject,
      plainText,
      options
    );
  } catch (error) {
    // Do not log the exception: provider messages can contain email content.
    return jsonResponse({ ok: false, error: "delivery_failed" });
  }

  return jsonResponse({ ok: true });
}


function validatePayload(payload) {
  if (!payload || typeof payload !== "object") {
    return "invalid_request";
  }

  if (!Array.isArray(payload.to) || payload.to.length < 1 ||
      payload.to.length > MAX_RECIPIENTS) {
    return "invalid_request";
  }
  for (var index = 0; index < payload.to.length; index += 1) {
    var recipient = payload.to[index];
    if (typeof recipient !== "string" || recipient.length > 254 ||
        !EMAIL_ADDRESS_PATTERN.test(recipient)) {
      return "invalid_request";
    }
  }

  if (typeof payload.subject !== "string" ||
      payload.subject.trim().length < 1 ||
      payload.subject.length > MAX_SUBJECT_LENGTH ||
      /[\x00-\x1f\x7f]/.test(payload.subject)) {
    return "invalid_request";
  }

  var hasText = typeof payload.text === "string";
  var hasHtml = typeof payload.html === "string";
  if ((!hasText && !hasHtml) ||
      (payload.text !== undefined && !hasText) ||
      (payload.html !== undefined && !hasHtml) ||
      (!payload.text && !payload.html)) {
    return "invalid_request";
  }

  var bodyBytes = 0;
  if (hasText) {
    bodyBytes += Utilities.newBlob(payload.text).getBytes().length;
  }
  if (hasHtml) {
    bodyBytes += Utilities.newBlob(payload.html).getBytes().length;
  }
  if (bodyBytes > MAX_BODY_BYTES) {
    return "invalid_request";
  }

  return "";
}


function constantTimeEquals(candidate, expected) {
  if (typeof candidate !== "string" || typeof expected !== "string" ||
      candidate.length > 256 || expected.length > 256) {
    return false;
  }

  var difference = candidate.length ^ expected.length;
  var length = Math.max(candidate.length, expected.length);
  for (var index = 0; index < length; index += 1) {
    var candidateCode = index < candidate.length
      ? candidate.charCodeAt(index)
      : 0;
    var expectedCode = index < expected.length
      ? expected.charCodeAt(index)
      : 0;
    difference |= candidateCode ^ expectedCode;
  }
  return difference === 0;
}


function htmlToPlainText(html) {
  return html
    .replace(/<br\s*\/?\s*>/gi, "\n")
    .replace(/<\/(p|div|li|tr)>/gi, "\n")
    .replace(/<[^>]*>/g, " ")
    .replace(/&nbsp;/gi, " ")
    .replace(/&amp;/gi, "&")
    .replace(/&lt;/gi, "<")
    .replace(/&gt;/gi, ">")
    .replace(/&quot;/gi, '"')
    .replace(/&#39;/gi, "'");
}


function jsonResponse(value) {
  return ContentService.createTextOutput(JSON.stringify(value))
    .setMimeType(ContentService.MimeType.JSON);
}
