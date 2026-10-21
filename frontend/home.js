const homeMessage = document.getElementById("homeMessage");
const savedBookmarks = new Map();

function formatPaperDate(value) {
    if (!value) return "DATE NOT LISTED";
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime())
        ? value
        : parsed.toLocaleDateString(undefined, {
            year: "numeric",
            month: "short",
            day: "numeric"
        }).toUpperCase();
}

function paperSummary(paper) {
    return window.summaryPresentation(
        paper.description || "No summary is available for this paper.",
        paper.summary_source
    );
}

function openPaper(paper) {
    sessionStorage.setItem("selectedPaper", JSON.stringify(paper));
    window.location.href = "paper.html";
}

function createPaperLink(paper, label = "Read paper ↗", className = "small-read") {
    const button = document.createElement("button");
    button.type = "button";
    button.className = className;
    button.textContent = label;
    button.addEventListener("click", () => openPaper(paper));
    return button;
}

async function toggleBookmark(paper, button) {
    if (!sessionStorage.getItem("token")) {
        sessionStorage.setItem("redirectAfterLogin", "home.html");
        window.location.href = "login.html";
        return;
    }

    button.disabled = true;
    try {
        const existing = savedBookmarks.get(paper.id);
        if (existing) {
            await window.apiRequest(`/bookmarks/${existing.id}`, { method: "DELETE" });
            savedBookmarks.delete(paper.id);
        } else {
            const result = await window.apiRequest("/bookmarks/", {
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
            savedBookmarks.set(paper.id, result);
        }
        button.textContent = savedBookmarks.has(paper.id) ? "Saved ✓" : "Save for later +";
        button.setAttribute("aria-pressed", String(savedBookmarks.has(paper.id)));
        homeMessage.textContent = savedBookmarks.has(paper.id)
            ? "Added to your reading list."
            : "Removed from your reading list.";
    } catch (error) {
        homeMessage.textContent = error.message;
        if (error.statusCode === 401) window.location.href = "login.html";
    } finally {
        button.disabled = false;
    }
}

function createSaveButton(paper) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "save-paper";
    button.textContent = savedBookmarks.has(paper.id) ? "Saved ✓" : "Save for later +";
    button.setAttribute("aria-pressed", String(savedBookmarks.has(paper.id)));
    button.addEventListener("click", () => toggleBookmark(paper, button));
    return button;
}

function showSectionError(element, message) {
    element.replaceChildren();
    element.setAttribute("aria-busy", "false");
    const paragraph = document.createElement("p");
    paragraph.className = "feed-error";
    paragraph.textContent = message;
    element.appendChild(paragraph);
}

function renderFeature(paper) {
    const element = document.querySelector(".feature-copy");
    element.setAttribute("aria-busy", "false");
    const title = document.getElementById("featureHeading");
    title.textContent = paper.title || "Untitled paper";
    const byline = element.querySelector(".feature-byline");
    byline.textContent = `${(paper.authors || []).slice(0, 3).join(", ") || "Authors not listed"} · ${formatPaperDate(paper.date)}`;
    const summary = element.querySelector(".feature-summary");
    const summaryView = paperSummary(paper);
    summary.textContent = summaryView.text;
    const actions = element.querySelector(".feature-actions");
    actions.replaceChildren();
    const source = document.createElement("span");
    source.className = "summary-source";
    source.textContent = summaryView.label;
    actions.append(source, createPaperLink(paper, "Open the paper ↗", "paper-read"));
    const save = createSaveButton(paper);
    actions.appendChild(save);
}

function renderBigIdea(paper) {
    const idea = document.querySelector(".big-idea-copy");
    idea.setAttribute("aria-busy", "false");
    const summaryView = paperSummary(paper);
    idea.querySelector(".big-idea-text").textContent = summaryView.text;
    idea.querySelector(".big-idea-source").textContent =
        `${summaryView.label} · ${paper.title || "Title unavailable"}`;
    const read = idea.querySelector(".big-idea-read");
    read.hidden = false;
    read.addEventListener("click", () => openPaper(paper));
}

function renderPaperCard(paper, index, className, options = {}) {
    const article = document.createElement("article");
    article.className = className;
    const number = document.createElement("span");
    number.className = "paper-index";
    number.textContent = options.label || `0${index + 1} / ARXIV`;
    const title = document.createElement("h3");
    title.textContent = paper.title || "Untitled paper";
    const authors = document.createElement("p");
    authors.className = "paper-authors";
    authors.textContent = (paper.authors || []).slice(0, 4).join(", ") || "Authors not listed";
    const summary = document.createElement("p");
    summary.className = "paper-summary";
    summary.textContent = paperSummary(paper).text;
    const footer = document.createElement("div");
    footer.className = "paper-bottom";
    const date = document.createElement("span");
    date.className = "paper-date";
    date.textContent = formatPaperDate(paper.date);
    const actions = document.createElement("span");
    actions.className = "paper-card-actions";
    actions.append(createPaperLink(paper));
    if (options.save !== false) actions.append(createSaveButton(paper));
    footer.append(date, actions);
    article.append(number, title, authors, summary);
    if (options.source) {
        const source = document.createElement("small");
        source.className = "summary-source";
        source.textContent = paperSummary(paper).label;
        article.appendChild(source);
    }
    article.appendChild(footer);
    return article;
}

function renderFresh(papers) {
    const element = document.getElementById("freshPapers");
    element.setAttribute("aria-busy", "false");
    element.replaceChildren();
    if (!papers.length) {
        showSectionError(element, "No recent papers were returned. Visit the live research feed to try again.");
        return;
    }
    papers.slice(0, 3).forEach((paper, index) => {
        element.appendChild(renderPaperCard(paper, index, "fresh-paper", {
            label: `${formatPaperDate(paper.date)} / ARXIV`
        }));
    });
    renderBigIdea(papers[0]);
}

function renderSurprise(paper) {
    const content = document.querySelector(".surprise-content");
    content.setAttribute("aria-busy", "false");
    const summary = content.querySelector(".surprise-summary");
    const summaryView = paperSummary(paper);
    summary.textContent = summaryView.text;
    const read = content.querySelector(".surprise-read");
    read.hidden = false;
    read.addEventListener("click", () => openPaper(paper));
    const source = document.createElement("p");
    source.className = "summary-source";
    source.textContent = `${summaryView.label} · ${paper.title || "Untitled paper"}`;
    content.insertBefore(source, read);
}

function renderKeep(papers) {
    const element = document.getElementById("keepPapers");
    element.setAttribute("aria-busy", "false");
    element.replaceChildren();
    if (!papers.length) {
        showSectionError(element, "No related papers were returned. Explore all fields in the feed.");
        return;
    }
    papers.slice(0, 2).forEach((paper, index) => {
        element.appendChild(renderPaperCard(paper, index, "keep-paper", {
            label: `ANOTHER THREAD / 0${index + 1}`
        }));
    });
}

async function fetchPapers(query, options = {}) {
    const params = new URLSearchParams({
        query,
        max_results: String(options.count || 3),
        sort_by: options.sort || "relevance"
    });
    const papers = await window.apiRequest(`/articles/live?${params}`);
    if (!Array.isArray(papers)) throw new Error("The research feed returned an invalid response.");
    return papers;
}

async function loadHomepage() {
    if (sessionStorage.getItem("token")) {
        try {
            const bookmarks = await window.apiRequest("/bookmarks/");
            bookmarks.forEach((item) => savedBookmarks.set(item.article_id, item));
        } catch (error) {
            homeMessage.textContent = error.statusCode === 401
                ? "Your session expired. Sign in again to use your reading list."
                : error.message;
        }
    }

    const jobs = [
        fetchPapers("", { count: 3, sort: "submittedDate" })
            .then((papers) => {
                renderFresh(papers);
                if (!papers.length) {
                    showSectionError(document.querySelector(".big-idea-copy"), "No recent paper was available. Explore the live feed for another idea.");
                }
            })
            .catch((error) => {
                showSectionError(document.getElementById("freshPapers"), error.message);
                showSectionError(document.querySelector(".big-idea-copy"), error.message);
            }),
        fetchPapers("computer vision", { count: 1 })
            .then((papers) => {
                if (papers.length) renderFeature(papers[0]);
                else showSectionError(document.querySelector(".feature-copy"), "No feature paper was returned. Browse the latest research feed.");
            })
            .catch((error) => showSectionError(document.querySelector(".feature-copy"), error.message)),
        fetchPapers("unexpected", { count: 1 })
            .then((papers) => {
                if (papers.length) renderSurprise(papers[0]);
                else showSectionError(document.querySelector(".surprise-content"), "No papers matched this search. Explore another field.");
            })
            .catch((error) => showSectionError(document.querySelector(".surprise-content"), error.message)),
        fetchPapers("neuroscience", { count: 2 })
            .then(renderKeep)
            .catch((error) => showSectionError(document.getElementById("keepPapers"), error.message))
    ];

    await Promise.all(jobs);
}

document.getElementById("homeSearchForm")?.addEventListener("submit", (event) => {
    event.preventDefault();
    const query = document.getElementById("homeSearchInput").value.trim();
    if (!query) return;
    sessionStorage.setItem("searchQuery", query);
    sessionStorage.setItem("category", "All");
    window.location.href = "index.html";
});

document.querySelectorAll("[data-category]").forEach((link) => {
    link.addEventListener("click", () => {
        sessionStorage.setItem("category", link.dataset.category);
    });
});

loadHomepage();
