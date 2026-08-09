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

    try {

        const response = await fetch(
            `http://127.0.0.1:8000/auth/verify-reset-otp?email=${encodeURIComponent(email)}&otp=${encodeURIComponent(otp)}`,
            {
                method: "POST"
            }
        );

        const data = await response.json();

        if (!response.ok) {
            message.textContent = data.detail;
            return;
        }

        // OTP is correct
        sessionStorage.setItem("otpVerified", "true");

        window.location.href = "reset-password.html";

    } catch (error) {

        console.error(error);
        message.textContent = "Something went wrong.";

    }

});