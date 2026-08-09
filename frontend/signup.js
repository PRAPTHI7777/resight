const signupForm = document.getElementById("signupForm");
const message = document.getElementById("message");

signupForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const username = document.getElementById("username").value;
    const email = document.getElementById("email").value;
    const password = document.getElementById("password").value;

    try {
        const response = await fetch(
            "http://127.0.0.1:8000/auth/send-otp",
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    username: username,
                    email: email,
                    password: password
                })
            }
        );

        const data = await response.json();

        if (!response.ok) {
            message.textContent = data.detail;
            return;
        }

        // Save the email temporarily so the OTP page knows
        // which account is being verified.
        sessionStorage.setItem("signupEmail", email);

        window.location.href = "verify-otp.html";

    } catch (error) {
        console.error(error);
        message.textContent = "Something went wrong.";
    }
});