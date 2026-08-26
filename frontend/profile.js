const token = sessionStorage.getItem("token");


// ------------------------------------
// Check Login
// ------------------------------------

if (!token) {

    window.location.href = "login.html";

}


// ------------------------------------
// Load User Information
// ------------------------------------

async function loadUser() {

    try {

        const response = await fetch(
            "http://127.0.0.1:8000/users/me",
            {
                headers: {
                    "Authorization": `Bearer ${token}`
                }
            }
        );


        if (!response.ok) {

            console.error("Could not load user");

            sessionStorage.clear();

            window.location.href = "login.html";

            return;
        }


        const data = await response.json();


        document.getElementById("username").textContent =
            data.username;

        document.getElementById("email").textContent =
            data.email;


    } catch (error) {

        console.error("User loading error:", error);

    }

}


// ------------------------------------
// Logout
// ------------------------------------

document.getElementById("logoutBtn").addEventListener(
    "click",
    () => {

        sessionStorage.clear();

        window.location.href = "login.html";

    }
);


// ------------------------------------
// Subscription
// ------------------------------------

const subscriptionStatus =
    document.getElementById("subscriptionStatus");

const subscriptionBtn =
    document.getElementById("subscriptionBtn");


let isSubscribed = false;


// ------------------------------------
// Get Subscription Status
// ------------------------------------

async function loadSubscription() {

    try {

        const response = await fetch(
            "http://127.0.0.1:8000/subscription/status",
            {
                headers: {
                    "Authorization": `Bearer ${token}`
                }
            }
        );


        if (!response.ok) {

            subscriptionStatus.textContent =
                "Could not load subscription status.";

            return;
        }


        const data = await response.json();


        console.log(
            "Subscription status:",
            data
        );


        isSubscribed = data.is_subscribed;


        updateSubscriptionUI();


    } catch (error) {

        console.error(
            "Subscription status error:",
            error
        );

    }

}


// ------------------------------------
// Update Subscription UI
// ------------------------------------

function updateSubscriptionUI() {

    if (isSubscribed) {

        subscriptionStatus.textContent =
            "You are subscribed to Resight digests.";

        subscriptionBtn.textContent =
            "Unsubscribe";

    } else {

        subscriptionStatus.textContent =
            "You are not subscribed to Resight digests.";

        subscriptionBtn.textContent =
            "Subscribe";

    }

}


// ------------------------------------
// Subscribe / Unsubscribe
// ------------------------------------

subscriptionBtn.addEventListener(
    "click",
    async () => {

        const endpoint = isSubscribed
            ? "/subscription/unsubscribe"
            : "/subscription/subscribe";


        console.log(
            "Calling:",
            endpoint
        );


        // Prevent multiple clicks while request is running

        subscriptionBtn.disabled = true;


        try {

            const response = await fetch(
                `http://127.0.0.1:8000${endpoint}`,
                {
                    method: "POST",

                    headers: {
                        "Authorization": `Bearer ${token}`
                    }
                }
            );


            const data = await response.json();


            console.log(
                "Subscription response:",
                data
            );


            if (!response.ok) {

                console.error(
                    "Subscription failed:",
                    data
                );

                subscriptionStatus.textContent =
                    "Something went wrong. Please try again.";

                return;
            }


            // Get the actual state returned by backend

            isSubscribed =
                data.is_subscribed;


            updateSubscriptionUI();


        } catch (error) {

            console.error(
                "Subscription error:",
                error
            );

            subscriptionStatus.textContent =
                "Something went wrong. Please try again.";

        } finally {

            subscriptionBtn.disabled = false;

        }

    }
);


// ------------------------------------
// Start
// ------------------------------------

loadUser();

loadSubscription();