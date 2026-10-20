const signupOtpForm = document.getElementById("signupOtpForm");
const signupOtpMessage = document.getElementById("message");
const signupEmail = sessionStorage.getItem("signupEmail");

if (!signupEmail) {
    signupOtpMessage.textContent = "Signup email not found. Please sign up again.";
    signupOtpForm.querySelector("button[type='submit']").disabled = true;
} else {
    document.getElementById("signupEmail").textContent = signupEmail;
}

signupOtpForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!signupEmail) return;

    const otp = document.getElementById("otp").value.trim();
    try {
        await window.apiRequest("/auth/verify-signup-otp", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email: signupEmail, otp })
        });
        sessionStorage.removeItem("signupEmail");
        signupOtpMessage.textContent = "Email verified. Redirecting to login...";
        setTimeout(() => {
            window.location.href = "login.html";
        }, 800);
    } catch (error) {
        signupOtpMessage.textContent = error.message;
    }
});

document.getElementById("resendSignupOtp").addEventListener("click", async () => {
    if (!signupEmail) return;
    try {
        await window.apiRequest("/auth/resend-signup-otp", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email: signupEmail })
        });
        signupOtpMessage.textContent = "A new verification code was sent.";
    } catch (error) {
        signupOtpMessage.textContent = error.message;
    }
});
