const token = sessionStorage.getItem("token");
const subscriptionStatus = document.getElementById("subscriptionStatus");
const subscriptionBtn = document.getElementById("subscriptionBtn");

if (!token) {
    window.location.href = "login.html";
}

async function loadProfile() {
    try {
        const [user, bookmarks, likes, subscription] = await Promise.all([
            window.apiRequest("/users/me"),
            window.apiRequest("/bookmarks/"),
            window.apiRequest("/likes/"),
            window.apiRequest("/subscription/status")
        ]);
        document.getElementById("username").textContent = user.username;
        document.getElementById("email").textContent = user.email;
        document.getElementById("bookmarkCount").textContent = bookmarks.length;
        document.getElementById("likeCount").textContent = likes.length;
        isSubscribed = subscription.is_subscribed;
        updateSubscriptionUI();
    } catch (error) {
        subscriptionStatus.textContent = error.message;
        if (error.statusCode === 401) {
            sessionStorage.removeItem("token");
            window.location.href = "login.html";
        }
    }
}

function updateSubscriptionUI() {
    subscriptionStatus.textContent = isSubscribed
        ? "You are subscribed to Resight digests."
        : "You are not subscribed to Resight digests.";
    subscriptionBtn.textContent = isSubscribed ? "Unsubscribe" : "Subscribe";
}

let isSubscribed = false;

document.getElementById("logoutBtn").addEventListener("click", () => {
    sessionStorage.clear();
    window.location.href = "login.html";
});

subscriptionBtn.addEventListener("click", async () => {
    subscriptionBtn.disabled = true;
    const endpoint = isSubscribed
        ? "/subscription/unsubscribe"
        : "/subscription/subscribe";
    try {
        const result = await window.apiRequest(endpoint, { method: "POST" });
        isSubscribed = result.is_subscribed;
        updateSubscriptionUI();
    } catch (error) {
        subscriptionStatus.textContent = error.message;
        if (error.statusCode === 401) {
            sessionStorage.removeItem("token");
            window.location.href = "login.html";
        }
    } finally {
        subscriptionBtn.disabled = false;
    }
});

if (token) loadProfile();
