(() => {
    const localHosts = new Set(["localhost", "127.0.0.1"]);
    const localDefault = localHosts.has(window.location.hostname)
        ? "http://127.0.0.1:8000"
        : "";
    const configuredBase = window.RESIGHT_API_BASE_URL || localDefault;

    window.RESIGHT_CONFIG = Object.freeze({
        apiBaseUrl: String(configuredBase).trim().replace(/\/+$/, "")
    });
})();
