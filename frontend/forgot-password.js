const forgotForm = document.getElementById("forgotForm");
const message = document.getElementById("message");

forgotForm.addEventListener("submit", async (event) => {

    event.preventDefault();

    const email = document.getElementById("email").value.trim();

    try {

        const response = await fetch(
            `http://127.0.0.1:8000/auth/forgot-password?email=${encodeURIComponent(email)}`,
            {
                method: "POST"
            }
        );

        const data = await response.json();

        if (!response.ok) {
            message.textContent = data.detail;
            return;
        }

        // Remember which email is being reset
        sessionStorage.setItem("resetEmail", email);

        // Go to OTP page
        window.location.href = "reset-otp.html";

    } catch (error) {

        console.error(error);
        message.textContent = "Something went wrong.";

    }
});