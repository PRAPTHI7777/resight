const container = document.getElementById("bookmarksContainer");
const status = document.getElementById("libraryMessage");
let savedItems = [];

function renderBookmarks(items) {
    container.replaceChildren();
    if (!items.length && !document.getElementById("librarySearch").value.trim()) {
        const empty = document.createElement("div");
        empty.className = "library-empty";
        empty.innerHTML = "<p class=\"eyebrow\">A NEW PAGE</p><h2>Your reading list is ready.</h2><p>Save a paper from the feed and it will be waiting here.</p><a href=\"index.html\">Explore papers ↗</a>";
        container.appendChild(empty);
        return;
    }
    if (!items.length) {
        const empty = document.createElement("p");
        empty.className = "library-empty";
        empty.textContent = "No saved papers match that search.";
        container.appendChild(empty);
        return;
    }

    for (const [index, item] of items.entries()) {
        const card = document.createElement("div");
        card.className = "bookmark-card library-card";
        const serial = document.createElement("small");
        serial.className = "library-serial";
        serial.textContent = `SAVED / ${String(index + 1).padStart(2, "0")}`;
        const title = document.createElement("h2");
        title.textContent = item.title || "Untitled paper";
        const authors = document.createElement("p");
        authors.textContent = (item.authors || []).join(", ");
        const summary = document.createElement("p");
        const summaryView = window.summaryPresentation(item.summary);
        summary.textContent = summaryView.text;
        const source = document.createElement("small");
        source.className = "summary-source";
        source.textContent = summaryView.label;
        const link = document.createElement("a");
        const isSafeLink = /^https?:\/\//i.test(item.link || "");
        if (isSafeLink) {
            link.href = item.link;
            link.target = "_blank";
            link.rel = "noopener noreferrer";
            link.textContent = "Read original ↗";
        }
        const open = document.createElement("button");
        open.type = "button";
        open.className = "library-open";
        open.textContent = "Open paper";
        open.addEventListener("click", () => {
            sessionStorage.setItem("selectedPaper", JSON.stringify({
                id: item.article_id,
                title: item.title,
                authors: item.authors || [],
                description: item.summary,
                summary_source: item.summary_source,
                link: isSafeLink ? item.link : "",
                date: "",
                category: ""
            }));
            window.location.href = "paper.html";
        });
        const remove = document.createElement("button");
        remove.type = "button";
        remove.textContent = "Remove Bookmark";
        remove.addEventListener("click", async () => {
            try {
                await window.apiRequest(`/bookmarks/${item.id}`, { method: "DELETE" });
                savedItems = savedItems.filter((saved) => saved.id !== item.id);
                card.remove();
                if (!container.querySelector(".library-card")) renderBookmarks([]);
            } catch (error) {
                status.textContent = error.message;
            }
        });
        const actions = document.createElement("div");
        actions.className = "library-actions";
        actions.append(open);
        if (isSafeLink) actions.append(link);
        actions.append(remove);
        card.append(serial, title, authors, summary, source, actions);
        container.appendChild(card);
    }
}

if (!sessionStorage.getItem("token")) {
    window.location.href = "login.html";
} else {
    status.textContent = "Loading your bookmarks...";
    window.apiRequest("/bookmarks/")
        .then((items) => {
            savedItems = items;
            renderBookmarks(savedItems);
            status.textContent = items.length ? `${items.length} saved ${items.length === 1 ? "paper" : "papers"}` : "";
        })
        .catch((error) => {
            status.textContent = error.message;
            if (error.statusCode === 401) window.location.href = "login.html";
        });
}

document.getElementById("librarySearch").addEventListener("input", (event) => {
    const query = event.target.value.trim().toLocaleLowerCase();
    renderBookmarks(savedItems.filter((item) =>
        `${item.title || ""} ${(item.authors || []).join(" ")}`.toLocaleLowerCase().includes(query)
    ));
});
