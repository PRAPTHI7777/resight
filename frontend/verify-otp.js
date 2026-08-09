const otpForm = document.getElementById("otpForm");
const otpMessage = document.getElementById("otpMessage");

otpForm.addEventListener("submit", async (event) => {

    event.preventDefault();

    const otp = document.getElementById("otp").value;
    const email = sessionStorage.getItem("signupEmail");

    if (!email) {
        otpMessage.textContent = "Email not found. Please sign up again.";
        return;
    }

    try {

        const response = await fetch(
            "http://127.0.0.1:8000/auth/verify-otp",
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    email: email,
                    otp: otp
                })
            }
        );

        const data = await response.json();

        if (!response.ok) {
            otpMessage.textContent = data.detail;
            return;
        }

        otpMessage.textContent = "Email verified successfully!";

        sessionStorage.removeItem("signupEmail");

        setTimeout(() => {
            window.location.href = "login.html";
        }, 1000);

    } catch (error) {

        console.error(error);
        otpMessage.textContent = "Something went wrong.";

    }

});