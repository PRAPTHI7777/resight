const token=sessionStorage.getItem("token");

fetch("http://127.0.0.1:8000/users/me",{
    headers:{
        Authorization:`Bearer ${token}`
    }
})
.then(res=>res.json())
.then(data=>{
    document.getElementById("username").textContent=data.username;
    document.getElementById("email").textContent=data.email;
});

document.getElementById("logoutBtn").addEventListener("click",()=>{
    sessionStorage.clear();
    window.location.href="login.html";
});