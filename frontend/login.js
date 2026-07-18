const form = document.getElementById("loginForm");

form.addEventListener("submit", async function(event) {
    event.preventDefault();

    const email = document.getElementById("email").value;
    const password = document.getElementById("password").value;

    const formData = new FormData();

formData.append("username", email);
formData.append("password", password);
const response = await fetch("http://127.0.0.1:8000/auth/login", {
    method: "POST",
    body: formData
    });
    const data = await response.json();

    if (response.ok) {
        sessionStorage.setItem("token", data.access_token);
        window.location.href = "index.html";
    } else {
        document.getElementById("message").innerText = data.detail;
    }
});