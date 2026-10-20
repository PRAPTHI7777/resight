async function removeBookmark(id, card) {
    try {
        await window.apiRequest(`/bookmarks/${id}`, { method: "DELETE" });
        card.remove();
        if (container.children.length === 0) {
            container.textContent = "No bookmarks yet.";
        }
    } catch (error) {
        alert(error.message);
    }
}
