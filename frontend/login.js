const form = document.getElementById("loginForm");

form.addEventListener("submit", async function (event) {
    event.preventDefault();
    const submit = form.querySelector("button[type='submit']");
    submit.disabled = true;
    submit.textContent = "Signing in...";

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
        const redirect = sessionStorage.getItem("redirectAfterLogin");
        sessionStorage.removeItem("redirectAfterLogin");
        window.location.href = redirect && /^[a-z0-9-]+\.html$/i.test(redirect)
            ? redirect
            : "index.html";
    } catch (error) {
        message.textContent = error.message;
    } finally {
        submit.disabled = false;
        submit.textContent = "Login";
    }
});