(() => {
    const localHosts = new Set(["localhost", "127.0.0.1"]);
    window.RESIGHT_API_BASE_URL = localHosts.has(window.location.hostname)
        ? "http://127.0.0.1:8000"
        : "https://resight.onrender.com";
})();
