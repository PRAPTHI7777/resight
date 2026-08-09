const resetForm = document.getElementById("resetForm");
const message = document.getElementById("message");

resetForm.addEventListener("submit", async (event) => {

    event.preventDefault();

    const newPassword = document.getElementById("newPassword").value;
    const confirmPassword = document.getElementById("confirmPassword").value;

    const email = sessionStorage.getItem("resetEmail");
    const otpVerified = sessionStorage.getItem("otpVerified");

    if (!email || otpVerified !== "true") {
        message.textContent = "Please verify your OTP first.";
        return;
    }

    if (newPassword !== confirmPassword) {
        message.textContent = "Passwords do not match.";
        return;
    }

    try {

        const response = await fetch(
            `http://127.0.0.1:8000/auth/reset-password?email=${encodeURIComponent(email)}&new_password=${encodeURIComponent(newPassword)}`,
            {
                method: "POST"
            }
        );

        const data = await response.json();

        if (!response.ok) {
            message.textContent = data.detail;
            return;
        }

        message.textContent = "Password reset successfully!";

        sessionStorage.removeItem("resetEmail");
        sessionStorage.removeItem("otpVerified");

        setTimeout(() => {
            window.location.href = "login.html";
        }, 1000);

    } catch (error) {

        console.error(error);
        message.textContent = "Something went wrong.";

    }

});