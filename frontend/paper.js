const storedPaper = sessionStorage.getItem("selectedPaper");
if (!storedPaper) {
    window.location.href = "index.html";
} else {
    try {
        const paper = JSON.parse(storedPaper);
        document.getElementById("title").textContent = paper.title || "Untitled paper";
        document.getElementById("authors").textContent =
            Array.isArray(paper.authors) ? paper.authors.join(", ") : "Unknown authors";
        document.getElementById("date").textContent = paper.date || "Unknown date";
        document.getElementById("category").textContent =
            paper.category || "Unknown category";
        document.getElementById("summary").textContent =
            paper.description || "No summary available.";
        document.getElementById("description").textContent =
            paper.abstract || "No abstract was provided by arXiv.";
        document.getElementById("summarySource").textContent =
            paper.summary_source === "abstract_fallback"
                ? "Abstract-based fallback summary (Gemini was unavailable)."
                : "Gemini-generated summary.";
        const paperLink = document.getElementById("paperLink");
        paperLink.href = paper.link;
        paperLink.rel = "noopener noreferrer";
    } catch {
        sessionStorage.removeItem("selectedPaper");
        window.location.href = "index.html";
    }
}
