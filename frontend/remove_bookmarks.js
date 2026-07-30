async function removeBookmark(id,card){

    const response=await fetch(
        `http://127.0.0.1:8000/bookmarks/${id}`,
        {
            method:"DELETE",
            headers:{
                Authorization:`Bearer ${token}`
            }
        }
    );

    if(response.ok){

        card.remove();

        if(container.children.length===0){
            container.innerHTML="<h2>No bookmarked papers yet.</h2>";
        }

    }else{

        alert("Failed to remove bookmark");

    }

}