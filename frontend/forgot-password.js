const forgotForm = document.getElementById("forgotForm");
const message = document.getElementById("message");

forgotForm.addEventListener("submit", async (event) => {

    event.preventDefault();

    const email = document.getElementById("email").value.trim();

    try {

        await window.apiRequest("/auth/forgot-password", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email })
        });

        // Remember which email is being reset
        sessionStorage.setItem("resetEmail", email);

        // Go to OTP page
        window.location.href = "reset-otp.html";

    } catch (error) {

        message.textContent = error.message;

    }
});