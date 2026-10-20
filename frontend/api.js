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
        throw requestError;
    }

    return payload;
};
