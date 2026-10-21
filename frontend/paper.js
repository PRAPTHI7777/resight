const storedPaper = sessionStorage.getItem("selectedPaper");
const paperContainer = document.querySelector(".paper-container");
const paperMessage = document.getElementById("paperMessage");

function openPaper(paper) {
    sessionStorage.setItem("selectedPaper", JSON.stringify(paper));
    window.location.href = "paper.html";
}

function setSavedState(button, isSaved, kind) {
    button.classList.toggle("is-selected", isSaved);
    button.setAttribute("aria-pressed", String(isSaved));
    button.setAttribute("aria-label", kind === "like"
        ? isSaved ? "Unlike paper" : "Like paper"
        : isSaved ? "Remove bookmark" : "Bookmark paper");
    button.querySelector("img").src = kind === "like"
        ? isSaved ? "icons/like2.png" : "icons/like1.png"
        : isSaved ? "icons/bookmrk2.png" : "icons/bookmrk1.png";
}

async function setPaperSaved(button, paper, kind, existing) {
    if (!sessionStorage.getItem("token")) {
        sessionStorage.setItem("redirectAfterLogin", "paper.html");
        window.location.href = "login.html";
        return;
    }
    button.disabled = true;
    const endpoint = kind === "like" ? "/likes" : "/bookmarks";
    try {
        if (existing.current) {
            await window.apiRequest(`${endpoint}/${existing.current.id}`, { method: "DELETE" });
            existing.current = null;
        } else {
            existing.current = await window.apiRequest(`${endpoint}/`, {
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
        }
        setSavedState(button, Boolean(existing.current), kind);
        paperMessage.textContent = existing.current
            ? `Added to your ${kind === "like" ? "likes" : "reading list"}.`
            : `Removed from your ${kind === "like" ? "likes" : "reading list"}.`;
    } catch (error) {
        paperMessage.textContent = error.message;
        if (error.statusCode === 401) {
            sessionStorage.removeItem("token");
            window.location.href = "login.html";
        }
    } finally {
        button.disabled = false;
    }
}

function renderRelated(papers, currentPaper) {
    const container = document.getElementById("relatedPapers");
    container.replaceChildren();
    container.setAttribute("aria-busy", "false");
    const related = papers.filter((paper) => paper.id !== currentPaper.id).slice(0, 2);
    if (!related.length) {
        const empty = document.createElement("p");
        empty.className = "feed-error";
        empty.textContent = "No related papers were found. Search the full index for another thread.";
        container.appendChild(empty);
        return;
    }
    related.forEach((paper, index) => {
        const card = document.createElement("article");
        card.className = "related-paper";
        const serial = document.createElement("span");
        serial.className = "related-serial";
        serial.textContent = `RELATED / 0${index + 1}`;
        const title = document.createElement("h3");
        title.textContent = paper.title || "Untitled paper";
        const authors = document.createElement("p");
        authors.textContent = (paper.authors || []).slice(0, 4).join(", ") || "Authors not listed";
        const summary = document.createElement("p");
        summary.textContent = window.summaryPresentation(
            paper.description,
            paper.summary_source
        ).text;
        const source = document.createElement("small");
        source.className = "summary-source";
        source.textContent = window.summaryPresentation(
            paper.description,
            paper.summary_source
        ).label;
        const read = document.createElement("button");
        read.type = "button";
        read.className = "related-read";
        read.textContent = "Open paper ↗";
        read.addEventListener("click", () => openPaper(paper));
        card.append(serial, title, authors, summary, source, read);
        container.appendChild(card);
    });
}

async function loadRelated(paper) {
    const container = document.getElementById("relatedPapers");
    const query = paper.category && paper.category !== "Search Results"
        ? paper.category.toLowerCase()
        : paper.title || "artificial intelligence";
    try {
        const params = new URLSearchParams({
            query,
            sort_by: "relevance",
            max_results: "3"
        });
        const papers = await window.apiRequest(`/articles/live?${params}`);
        if (!Array.isArray(papers)) throw new Error("The related-paper response was invalid.");
        renderRelated(papers, paper);
    } catch (error) {
        container.setAttribute("aria-busy", "false");
        container.replaceChildren();
        const message = document.createElement("p");
        message.className = "feed-error";
        message.textContent = error.message;
        container.appendChild(message);
    }
}

async function initPaper() {
    if (!storedPaper) {
        window.location.replace("index.html");
        return;
    }
    let paper;
    try {
        paper = JSON.parse(storedPaper);
        if (!paper || typeof paper !== "object" || !paper.title) {
            throw new Error("Invalid paper");
        }
    } catch {
        sessionStorage.removeItem("selectedPaper");
        window.location.replace("index.html");
        return;
    }

    document.title = `${paper.title} | ReSight`;
    document.getElementById("title").textContent = paper.title;
    document.getElementById("authors").textContent =
        Array.isArray(paper.authors) && paper.authors.length
            ? paper.authors.join(", ")
            : "Authors not listed";
    document.getElementById("date").textContent = paper.date || "Publication date unavailable";
    document.getElementById("category").textContent = paper.category || "Research paper";
    const summary = window.summaryPresentation(
        paper.description || "No summary is available for this paper.",
        paper.summary_source
    );
    document.getElementById("summary").textContent = summary.text;
    document.getElementById("summarySource").textContent = summary.label;
    document.getElementById("description").textContent =
        paper.abstract || "The source did not provide an abstract.";
    const sourceLink = document.getElementById("paperLink");
    if (paper.link && /^https?:\/\//i.test(paper.link)) {
        sourceLink.href = paper.link;
    } else {
        sourceLink.hidden = true;
    }
    paperContainer.setAttribute("aria-busy", "false");

    const existing = {
        like: { current: null },
        bookmark: { current: null }
    };
    const likeButton = document.getElementById("likePaper");
    const bookmarkButton = document.getElementById("bookmarkPaper");
    if (paper.id && sessionStorage.getItem("token")) {
        try {
            const [likes, bookmarks] = await Promise.all([
                window.apiRequest("/likes/"),
                window.apiRequest("/bookmarks/")
            ]);
            existing.like.current = likes.find((item) => item.article_id === paper.id) || null;
            existing.bookmark.current = bookmarks.find((item) => item.article_id === paper.id) || null;
            setSavedState(likeButton, Boolean(existing.like.current), "like");
            setSavedState(bookmarkButton, Boolean(existing.bookmark.current), "bookmark");
        } catch (error) {
            paperMessage.textContent = error.statusCode === 401
                ? "Your session expired. Sign in again to save this paper."
                : error.message;
        }
    }
    likeButton.addEventListener("click", () => setPaperSaved(
        likeButton, paper, "like", existing.like
    ));
    bookmarkButton.addEventListener("click", () => setPaperSaved(
        bookmarkButton, paper, "bookmark", existing.bookmark
    ));
    await loadRelated(paper);
}

initPaper();
