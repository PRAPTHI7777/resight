const form = document.getElementById("loginForm");

form.addEventListener("submit", async function (event) {
    event.preventDefault();

    const email = document.getElementById("email").value;
    const password = document.getElementById("password").value;

    const formData = new FormData();
    formData.append("username", email);
    formData.append("password", password);

    const message = document.getElementById("message");
    try {
        const data = await window.apiRequest("/auth/login", {
            method: "POST",
            body: formData
        });
        sessionStorage.setItem("token", data.access_token);
        window.location.href = "index.html";
    } catch (error) {
        message.textContent = error.message;
    }
});