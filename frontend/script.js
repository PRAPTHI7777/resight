const container = document.querySelector(".contain");
const feedMessage = document.getElementById("feedMessage");
const resultCount = document.getElementById("resultCount");
const searchQueries = {
    "All": "",
    "Artificial Intelligence": "artificial intelligence",
    "Neuroscience": "neuroscience",
    "Robotics": "robotics",
    "Computer Vision": "computer vision",
    "Cybersecurity": "cybersecurity",
    "Quantum Computing": "quantum computing",
    "Software": "software engineering",
    "Energy Tech": "renewable energy"
};
let savedLikes = new Map();
let savedBookmarks = new Map();
let activeQuery = "";

function setStatus(message, isError = false) {
    feedMessage.textContent = message;
    feedMessage.classList.toggle("is-error", isError);
}

function createActionButton({ label, selected, icon, kind }) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `${kind}-btn${selected ? " is-selected" : ""}`;
    button.setAttribute("aria-label", label);
    button.setAttribute("aria-pressed", String(selected));
    const image = document.createElement("img");
    image.src = icon;
    image.alt = "";
    image.setAttribute("aria-hidden", "true");
    button.appendChild(image);
    return button;
}

async function toggleSavedPaper(button, paper, collection, endpoint, kind) {
    if (!sessionStorage.getItem("token")) {
        sessionStorage.setItem("redirectAfterLogin", "index.html");
        window.location.href = "login.html";
        return;
    }
    button.disabled = true;
    try {
        const existing = collection.get(paper.id);
        if (existing) {
            await window.apiRequest(`${endpoint}/${existing.id}`, { method: "DELETE" });
            collection.delete(paper.id);
        } else {
            const result = await window.apiRequest(`${endpoint}/`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    article_id: paper.id,
                    title: paper.title,
                    authors: paper.authors || [],
                    summary: window.formatSummaryForStorage(paper),
                    link: paper.link
                })
            });
            collection.set(paper.id, result);
        }
        const selected = collection.has(paper.id);
        button.classList.toggle("is-selected", selected);
        button.setAttribute("aria-pressed", String(selected));
        button.setAttribute("aria-label", kind === "like"
            ? selected ? "Unlike paper" : "Like paper"
            : selected ? "Remove bookmark" : "Bookmark paper");
        button.querySelector("img").src = kind === "like"
            ? selected ? "icons/like2.png" : "icons/like1.png"
            : selected ? "icons/bookmrk2.png" : "icons/bookmrk1.png";
        setStatus(selected
            ? `Added to your ${kind === "like" ? "likes" : "reading list"}.`
            : `Removed from your ${kind === "like" ? "likes" : "reading list"}.`);
    } catch (error) {
        setStatus(error.message, true);
        if (error.statusCode === 401) {
            sessionStorage.removeItem("token");
            window.location.href = "login.html";
        }
    } finally {
        button.disabled = false;
    }
}

function openPaper(paper) {
    sessionStorage.setItem("selectedPaper", JSON.stringify(paper));
    window.location.href = "paper.html";
}

function renderPaper(paper, index) {
    const card = document.createElement("article");
    card.className = `paper-card${index === 0 ? " is-lead" : ""}`;
    const cover = document.createElement("div");
    cover.className = "card-serial";
    const serialLabel = document.createElement("span");
    serialLabel.textContent = "FIELD NOTE";
    const serialNumber = document.createElement("b");
    serialNumber.textContent = String(index + 1).padStart(2, "0");
    cover.append(serialLabel, serialNumber);
    const content = document.createElement("div");
    content.className = "card-content";
    const meta = document.createElement("div");
    meta.className = "card-meta";
    const category = document.createElement("span");
    category.textContent = paper.category || "Research";
    const date = document.createElement("span");
    date.textContent = paper.date || "Date unavailable";
    meta.append(category, date);

    const title = document.createElement("h2");
    title.textContent = paper.title || "Untitled paper";
    const authors = document.createElement("p");
    authors.className = "card-authors";
    authors.textContent = Array.isArray(paper.authors) && paper.authors.length
        ? paper.authors.join(", ")
        : "Authors not listed";
    const summary = document.createElement("p");
    summary.className = "card-summary";
    summary.textContent = window.summaryPresentation(
        paper.description || "No summary is available.",
        paper.summary_source
    ).text;
    const source = document.createElement("small");
    source.className = "summary-source";
    source.textContent = window.summaryPresentation(
        paper.description,
        paper.summary_source
    ).label;
    const actions = document.createElement("div");
    actions.className = "card-actions";
    const like = createActionButton({
        label: savedLikes.has(paper.id) ? "Unlike paper" : "Like paper",
        selected: savedLikes.has(paper.id),
        icon: savedLikes.has(paper.id) ? "icons/like2.png" : "icons/like1.png",
        kind: "like"
    });
    const bookmark = createActionButton({
        label: savedBookmarks.has(paper.id) ? "Remove bookmark" : "Bookmark paper",
        selected: savedBookmarks.has(paper.id),
        icon: savedBookmarks.has(paper.id) ? "icons/bookmrk2.png" : "icons/bookmrk1.png",
        kind: "bookmark"
    });
    like.addEventListener("click", () => toggleSavedPaper(like, paper, savedLikes, "/likes", "like"));
    bookmark.addEventListener("click", () => toggleSavedPaper(bookmark, paper, savedBookmarks, "/bookmarks", "bookmark"));
    const read = document.createElement("button");
    read.type = "button";
    read.className = "read-paper";
    read.textContent = "Read the paper ↗";
    read.addEventListener("click", () => openPaper(paper));
    actions.append(like, bookmark, read);
    content.append(meta, title, authors, summary, source, actions);
    card.append(cover, content);
    return card;
}

async function fetchArticles() {
    const category = document.getElementById("categoryselect").value;
    const selectedQuery = Object.prototype.hasOwnProperty.call(searchQueries, category)
        ? searchQueries[category]
        : category;
    const query = activeQuery || selectedQuery || "";
    const sort = document.getElementById("sortSelect").value;
    const count = Number(document.getElementById("countSelect").value);
    const params = new URLSearchParams({
        query,
        sort_by: sort,
        max_results: String(count)
    });
    container.replaceChildren();
    container.setAttribute("aria-busy", "true");
    resultCount.textContent = "";
    setStatus("Searching the arXiv index…");
    try {
        const papers = await window.apiRequest(`/articles/live?${params}`);
        if (!Array.isArray(papers)) throw new Error("The research feed returned an invalid response.");
        savedLikes = new Map();
        savedBookmarks = new Map();
        if (sessionStorage.getItem("token")) {
            try {
                const [likes, bookmarks] = await Promise.all([
                    window.apiRequest("/likes/"),
                    window.apiRequest("/bookmarks/")
                ]);
                savedLikes = new Map(likes.map((item) => [item.article_id, item]));
                savedBookmarks = new Map(bookmarks.map((item) => [item.article_id, item]));
            } catch (error) {
                if (error.statusCode === 401) {
                    setStatus("Your session expired. Sign in again to use your reading list.", true);
                } else {
                    setStatus(error.message, true);
                }
            }
        }
        container.replaceChildren(...papers.map(renderPaper));
        resultCount.textContent = `${papers.length} ${papers.length === 1 ? "paper" : "papers"}`;
        if (!papers.length) setStatus("No papers found. Try a broader search or a different field.");
        else if (!feedMessage.classList.contains("is-error")) setStatus("");
    } catch (error) {
        container.replaceChildren();
        setStatus(error.message, true);
    } finally {
        container.setAttribute("aria-busy", "false");
    }
}

document.querySelectorAll("nav a[data-category]").forEach((link) => {
    link.addEventListener("click", (event) => {
        event.preventDefault();
        document.getElementById("categoryselect").value = link.dataset.category;
        activeQuery = "";
        fetchArticles();
    });
});

document.getElementById("searchForm").addEventListener("submit", (event) => {
    event.preventDefault();
    activeQuery = document.getElementById("searchInput").value.trim();
    document.getElementById("categoryselect").value = "All";
    sessionStorage.setItem("searchQuery", activeQuery);
    fetchArticles();
});

document.getElementById("categoryselect").addEventListener("change", () => {
    activeQuery = "";
    sessionStorage.setItem("category", document.getElementById("categoryselect").value);
    document.getElementById("searchInput").value = "";
    sessionStorage.removeItem("searchQuery");
    fetchArticles();
});
document.getElementById("sortSelect").addEventListener("change", fetchArticles);
document.getElementById("countSelect").addEventListener("change", fetchArticles);

const savedCategory = sessionStorage.getItem("category") || "All";
document.getElementById("categoryselect").value =
    Object.prototype.hasOwnProperty.call(searchQueries, savedCategory) ? savedCategory : "All";
const savedQuery = sessionStorage.getItem("searchQuery");
if (savedQuery) {
    activeQuery = savedQuery;
    document.getElementById("searchInput").value = savedQuery;
    sessionStorage.removeItem("searchQuery");
    sessionStorage.removeItem("category");
}
fetchArticles();
