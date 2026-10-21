const otpForm = document.getElementById("otpForm");
const message = document.getElementById("message");

otpForm.addEventListener("submit", async (event) => {

    event.preventDefault();

    const otp = document.getElementById("otp").value.trim();
    const email = sessionStorage.getItem("resetEmail");

    if (!email) {
        message.textContent = "Email not found. Please start again.";
        return;
    }

    const submit = otpForm.querySelector("button[type='submit']");
    submit.disabled = true;
    submit.textContent = "Verifying...";
    try {

        await window.apiRequest("/auth/verify-reset-otp", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, otp })
        });

        // OTP is correct
        sessionStorage.setItem("otpVerified", "true");

        window.location.href = "reset-password.html";

    } catch (error) {

        message.textContent = error.message;

    } finally {
        submit.disabled = false;
        submit.textContent = "Verify OTP";
    }

});