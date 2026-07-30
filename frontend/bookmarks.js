const token=sessionStorage.getItem("token");

const container=document.getElementById("bookmarksContainer");

fetch("http://127.0.0.1:8000/bookmarks",{
    headers:{
        Authorization:`Bearer ${token}`
    }
})
.then(res=>res.json())
.then(data=>{

    container.innerHTML="";

    if(data.length===0){

        container.innerHTML="<h2>No bookmarks yet.</h2>";

        return;

    }
    data.forEach(item=>{
        const card=document.createElement("div");
        card.className="bookmark-card";
        card.innerHTML=`
        <h2>${item.title}</h2>
        <p>${item.authors.join(", ")}</p>
        <p>${item.summary}</p>
        <a href="${item.link}" target="_blank">
        Read Original Paper
        </a>
        <br><br>
        <button onclick="removeBookmark(${item.id})">
        Remove Bookmark
        </button>

        `;
        container.appendChild(card);
    });

});

async function removeBookmark(id){
    const response=await fetch(`http://127.0.0.1:8000/bookmarks/${id}`,
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