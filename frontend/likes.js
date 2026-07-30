const token=sessionStorage.getItem("token");

const container=document.getElementById("likesContainer");

fetch("http://127.0.0.1:8000/likes",{
    headers:{
        Authorization:`Bearer ${token}`
    }
})
.then(res=>res.json())
.then(data=>{

    container.innerHTML="";

    if(data.length===0){

        container.innerHTML="<h2>No Likes yet.</h2>";

        return;

    }
    data.forEach(item=>{
        const card=document.createElement("div");
        card.className="likes-card";
        card.innerHTML=`
        <h2>${item.title}</h2>
        <p>${item.authors.join(", ")}</p>
        <p>${item.summary}</p>
        <a href="${item.link}" target="_blank">
        Read Original Paper
        </a>
        <br><br>
        <button onclick="removeLike(${item.id})">
        Remove Like
        </button>

        `;
        container.appendChild(card);
    });

});

async function removeLike(id){
    const response=await fetch(`http://127.0.0.1:8000/likes/${id}`,
{
            method:"DELETE",
            headers:{
                Authorization:`Bearer ${token}`
            }
        }
    );
    if(response.ok){
        location.reload();
    }
}