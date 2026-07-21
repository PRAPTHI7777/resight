const form = document.getElementById("signupForm");

form.addEventListener("submit", async function (event) {
    event.preventDefault();

    const username = document.getElementById("username").value;
    const email = document.getElementById("email").value;
    const password = document.getElementById("password").value;

    const response = await fetch("http://127.0.0.1:8000/auth/signup", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            username: username,
            email: email,
            password: password
        })
    });

    const data = await response.json();

    if (response.ok) {
        alert("Account created successfully!");
        window.location.href = "login.html";
    } else {
        alert(data.detail);
    }
});