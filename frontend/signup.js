const signupForm = document.getElementById("signupForm");
const message = document.getElementById("message");

signupForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const submit = signupForm.querySelector("button[type='submit']");
    submit.disabled = true;
    submit.textContent = "Creating account...";

    const username = document.getElementById("username").value.trim();
    const email = document.getElementById("email").value.trim();
    const password = document.getElementById("password").value;

    try {
        await window.apiRequest("/auth/signup", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username, email, password })
        });

        sessionStorage.setItem("signupEmail", email);
        window.location.href = "otp.html";

    } catch (error) {
        message.textContent = error.message;
    } finally {
        submit.disabled = false;
        submit.textContent = "Sign Up";
    }
});