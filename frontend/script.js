const container = document.querySelector(".contain");
const feedMessage = document.getElementById("feedMessage");

const searchQueries = {
    "All": "artificial intelligence",
    "Artificial Intelligence": "artificial intelligence",
    "Robotics": "robotics",
    "Cybersecurity": "cybersecurity",
    "Quantum Computing": "quantum computing",
    "Software": "software engineering",
    "Energy Tech": "renewable energy"
};

function makeButton(label, className, imagePath, imageAlt) {
    const button = document.createElement("button");
    button.className = className;
    const image = document.createElement("img");
    image.src = imagePath;
    image.alt = imageAlt;
    button.appendChild(image);
    return { button, image };
}

function showFeedError(message) {
    feedMessage.textContent = message;
}

function renderCharacters(papers) {
    container.replaceChildren();
    for (const paper of papers) {
        const card = document.createElement("div");
        card.className = "container";

        const picture = document.createElement("div");
        picture.className = "picture";

        const content = document.createElement("div");
        content.className = "verticalcontain";

        const title = document.createElement("div");
        title.className = "title";
        title.textContent = paper.title || "No Title";

        const authors = document.createElement("div");
        authors.className = "authors";
        authors.textContent = Array.isArray(paper.authors)
            ? `- ${paper.authors.join(", ")}`
            : "- Unknown Author";

        const summary = document.createElement("div");
        summary.className = "summary";
        summary.textContent = paper.description || "No Description";

        const fallbackNote = document.createElement("small");
        fallbackNote.textContent = paper.summary_source === "abstract_fallback"
            ? "Abstract-based fallback summary"
            : "";

        const footer = document.createElement("div");
        footer.className = "footer-row";
        const date = document.createElement("div");
        date.className = "date";
        date.textContent = paper.date || "Unknown Date";
        const category = document.createElement("div");
        category.className = "category";
        category.textContent = paper.category || "Unknown Category";
        const actions = document.createElement("div");
        actions.className = "actions-group";

        const like = makeButton("Like", "like-btn", "icons/like1.png", "Like");
        const bookmark = makeButton(
            "Bookmark",
            "bookmark-btn",
            "icons/bookmrk1.png",
            "Bookmark"
        );
        const read = document.createElement("button");
        read.className = "read-btn";
        read.textContent = "Read More";
        read.addEventListener("click", () => {
            sessionStorage.setItem("selectedPaper", JSON.stringify(paper));
            window.location.href = "paper.html";
        });

        like.button.addEventListener("click", async () => {
            if (!sessionStorage.getItem("token")) {
                window.location.href = "login.html";
                return;
            }
            try {
                await window.apiRequest("/likes/", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        article_id: paper.id,
                        title: paper.title,
                        authors: paper.authors || [],
                        summary: paper.description || "",
                        link: paper.link
                    })
                });
                like.image.src = "icons/like2.png";
                like.button.disabled = true;
                showFeedError("Paper added to your likes.");
            } catch (error) {
                showFeedError(error.message);
            }
        });

        bookmark.button.addEventListener("click", async () => {
            if (!sessionStorage.getItem("token")) {
                window.location.href = "login.html";
                return;
            }
            try {
                await window.apiRequest("/bookmarks/", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        article_id: paper.id,
                        title: paper.title,
                        authors: paper.authors || [],
                        summary: paper.description || "",
                        link: paper.link
                    })
                });
                bookmark.image.src = "icons/bookmrk2.png";
                bookmark.button.disabled = true;
                showFeedError("Paper added to your bookmarks.");
            } catch (error) {
                showFeedError(error.message);
            }
        });

        actions.append(like.button, bookmark.button, read);
        footer.append(date, category, actions);
        content.append(title, authors, summary, fallbackNote, footer);
        card.append(picture, content);
        container.appendChild(card);
    }
}

async function fetchArticles(category) {
    const query = searchQueries[category] || category || searchQueries.All;
    const url = `/articles/live?query=${encodeURIComponent(query)}`;
    showFeedError("Loading papers...");
    try {
        const papers = await window.apiRequest(url);
        if (!Array.isArray(papers)) {
            throw new Error("The research feed returned an invalid response.");
        }
        renderCharacters(papers);
        showFeedError(papers.length ? "" : "No papers were found.");
    } catch (error) {
        showFeedError(error.message);
    }
}

function onCategoryClick(category) {
    sessionStorage.setItem("category", category);
    fetchArticles(category);
}

function filterByCategory(category) {
    sessionStorage.setItem("category", category);
    const dropdown = document.getElementById("categoryselect");
    if (dropdown) dropdown.value = category;
    fetchArticles(category);
}

document.addEventListener("DOMContentLoaded", () => {
    const dropdown = document.getElementById("categoryselect");
    const savedCategory = sessionStorage.getItem("category") || "All";
    if (dropdown) dropdown.value = savedCategory;
    const searchInput = document.getElementById("searchInput");
    const savedQuery = sessionStorage.getItem("searchQuery");
    if (savedQuery && searchInput) {
        searchInput.value = savedQuery;
        sessionStorage.removeItem("searchQuery");
        fetchArticles(savedQuery);
    } else {
        fetchArticles(savedCategory);
    }

    if (searchInput) {
        searchInput.addEventListener("keydown", (event) => {
            if (event.key !== "Enter") return;
            const query = searchInput.value.trim();
            if (query) fetchArticles(query);
        });
    }
});
