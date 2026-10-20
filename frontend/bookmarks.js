const container = document.getElementById("bookmarksContainer");

function renderBookmarks(items) {
    container.replaceChildren();
    if (!items.length) {
        container.textContent = "No bookmarks yet.";
        return;
    }

    for (const item of items) {
        const card = document.createElement("div");
        card.className = "bookmark-card";
        const title = document.createElement("h2");
        title.textContent = item.title;
        const authors = document.createElement("p");
        authors.textContent = (item.authors || []).join(", ");
        const summary = document.createElement("p");
        summary.textContent = item.summary;
        const link = document.createElement("a");
        link.href = item.link;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.textContent = "Read Original Paper";
        const remove = document.createElement("button");
        remove.type = "button";
        remove.textContent = "Remove Bookmark";
        remove.addEventListener("click", async () => {
            try {
                await window.apiRequest(`/bookmarks/${item.id}`, { method: "DELETE" });
                card.remove();
                if (!container.children.length) container.textContent = "No bookmarks yet.";
            } catch (error) {
                status.textContent = error.message;
            }
        });
        card.append(title, authors, summary, link, remove);
        container.appendChild(card);
    }
}

const status = document.createElement("p");
status.setAttribute("role", "status");
container.before(status);

if (!sessionStorage.getItem("token")) {
    window.location.href = "login.html";
} else {
    window.apiRequest("/bookmarks/")
        .then(renderBookmarks)
        .catch((error) => {
            status.textContent = error.message;
            if (error.statusCode === 401) window.location.href = "login.html";
        });
}
