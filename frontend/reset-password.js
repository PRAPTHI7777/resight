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

        await window.apiRequest("/auth/reset-password", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, new_password: newPassword })
        });

        message.textContent = "Password reset successfully!";

        sessionStorage.removeItem("resetEmail");
        sessionStorage.removeItem("otpVerified");

        setTimeout(() => {
            window.location.href = "login.html";
        }, 1000);

    } catch (error) {

        message.textContent = error.message;

    }

});