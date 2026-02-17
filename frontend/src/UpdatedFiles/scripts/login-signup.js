function showSignup() {
    document.getElementById('loginForm').classList.add('hidden');
    document.getElementById('signupForm').classList.remove('hidden');
}

function showLogin() {
    document.getElementById('signupForm').classList.add('hidden');
    document.getElementById('loginForm').classList.remove('hidden');
}

document.addEventListener("DOMContentLoaded", () => {
    const loginForm = document.getElementById("loginFormElement");
    const signupForm = document.getElementById("signupFormElement");

    if (loginForm) {
        loginForm.addEventListener("submit", function (e) {
            e.preventDefault();

            const email = document.getElementById("loginEmail").value;
            const password = document.getElementById("loginPassword").value;

            console.log("LOGIN ATTEMPT:", { email, password });

            window.location.href = "dashboard.html";
        });
    }

    if (signupForm) {
        signupForm.addEventListener("submit", function (e) {
            e.preventDefault();

            const name = document.getElementById("name").value;
            const email = document.getElementById("signupEmail").value;
            const department = document.getElementById("department").value;
            const password = document.getElementById("signupPassword").value;

            console.log("SIGNUP REQUEST:", { name, email, department, password });

            alert("Account request submitted for approval.");
            showLogin();
        });
    }
});
