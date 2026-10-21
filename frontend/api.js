window.apiRequest = async function (path, options = {}) {
    const headers = new Headers(options.headers || {});
    const token = sessionStorage.getItem("token");
    if (token && !headers.has("Authorization")) {
        headers.set("Authorization", `Bearer ${token}`);
    }

    let response;
    let payload = null;
    try {
        response = await fetch(`${window.RESIGHT_CONFIG.apiBaseUrl}${path}`, {
            ...options,
            headers
        });

        if (response.status !== 204) {
            const body = await response.text();
            if (body) {
                try {
                    payload = JSON.parse(body);
                } catch (error) {
                    if (response.ok) {
                        throw new Error("The server returned an invalid response.");
                    }
                }
            }
        }
    } catch (error) {
        if (error instanceof TypeError) {
            throw new Error("Could not reach the Resight API. Check your connection and API URL.");
        }
        throw error;
    }

    if (!response.ok) {
        const detail = payload && typeof payload.detail === "string"
            ? payload.detail
            : `Request failed with status ${response.status}.`;
        const requestError = new Error(detail);
        requestError.statusCode = response.status;
        if (response.status === 401 && token) {
            sessionStorage.removeItem("token");
        }
        throw requestError;
    }

    return payload;
};

window.limitSummaryWords = function (summary, limit = 60) {
    return String(summary || "").trim().split(/\s+/).filter(Boolean).slice(0, limit).join(" ");
};

window.summaryPresentation = function (summary, source) {
    const value = String(summary || "").trim();
    const markers = [
        ["[Abstract-based fallback]", "Abstract-based fallback"],
        ["[AI-generated]", "AI-generated summary"]
    ];
    const marker = markers.find(([prefix]) => value.startsWith(prefix));
    const text = marker ? value.slice(marker[0].length).trim() : value;
    const label = marker ? marker[1] : source === "abstract_fallback"
        ? "Abstract-based fallback"
        : source === "gemini"
            ? "AI-generated summary"
            : "Summary source not recorded";
    return { text: window.limitSummaryWords(text), label };
};

window.formatSummaryForStorage = function (paper) {
    const fallback = paper.summary_source === "abstract_fallback";
    const marker = fallback ? "[Abstract-based fallback]" : "[AI-generated]";
    const maxTextWords = fallback ? 58 : 59;
    const text = window.limitSummaryWords(paper.description, maxTextWords);
    return `${marker} ${text}`.trim();
};
