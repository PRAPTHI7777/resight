//Fetch data from local JSON file and render it to HTML document by using Vanilla JavaScript
const container=document.querySelector('.contain');

function renderCharacters(data){
    container.innerHTML = '';
    
    data.forEach(item => {
        console.log(item.id);
        // 1. Structural Elements
        const itemDiv = document.createElement('div');
        const pict = document.createElement('div');
        const verticle = document.createElement('div');
        const footerRow = document.createElement("div"); 
        const actionsGroup = document.createElement("div");
        
        // 2. Data Content Elements
        const titleDiv = document.createElement('div');
        const authorDiv = document.createElement('div');
        const summaryDiv = document.createElement('div');
        const dateDiv = document.createElement('div');
        const categoryDiv = document.createElement('div');
        
        // 3. Like Button (Configured with an Image instead of text)
        const likeBtn = document.createElement("button");
        likeBtn.className = "like-btn";
        
        const likeImg = document.createElement("img");
        likeImg.src = 'icons/likebtn1.jpg'; // Your default unliked image
        likeImg.alt = "like";
        likeImg.style.width = "45px";
        likeImg.style.height = "40px";
        likeBtn.appendChild(likeImg);
        
        // 4. Bookmark Button
        const bookmarkBtn = document.createElement("button");
        bookmarkBtn.className = "bookmark-btn";
        
        const bookmarkImg = document.createElement("img");
        bookmarkImg.src = 'icons/1.jpg'; // Your default unbookmarked image
        bookmarkImg.alt = "Bookmark button";
        bookmarkImg.style.width = "20px";
        bookmarkImg.style.height = "25px";
        bookmarkBtn.appendChild(bookmarkImg); 

        // 5. Apply CSS Classes
        itemDiv.className = 'container';
        pict.className = 'picture';
        verticle.className = 'verticalcontain';
        actionsGroup.className = "actions-group";
        footerRow.className = 'footer-row'; 
        titleDiv.className = 'title';
        authorDiv.className = 'authors';
        summaryDiv.className = 'summary';
        dateDiv.className = 'date';
        categoryDiv.className = 'category';

        // 6. Populate Text Content
        titleDiv.textContent = item.title || "No Title";
        
        if (Array.isArray(item.authors)) {
            authorDiv.textContent = '- ' + item.authors.join(', ');
        } else {
            authorDiv.textContent = '- Unknown Author';
        }
        
        summaryDiv.textContent = item.description || "No Description";
        dateDiv.textContent = item.date || "Unknown Date";
        categoryDiv.textContent = item.category || "Unknown Category";

        // 7. Event Listeners (Image Toggle Logic)
        likeBtn.addEventListener("click", () => {
            // Checks if the file path contains your default file name
            if (likeImg.src.includes('likebtn1.jpg')) {
                likeImg.src = 'icons/likebtn2.jpg'; // Swaps to active state image
            } else {
                likeImg.src = 'icons/likebtn1.jpg'; // Swaps back
            }
        });

        bookmarkBtn.addEventListener("click",async () => {
            const token = sessionStorage.getItem("token");

            if (!token) {
            alert("Please login to bookmark papers.");
            window.location.href = "login.html";
            return;
           }
  const response = await fetch("http://127.0.0.1:8000/bookmarks", {
    method: "POST",
    headers: {
        "Authorization": `Bearer ${token}`,
        "Content-Type": "application/json"
    },
    body: JSON.stringify({
        article_id: item.id
    })
});

if(response.ok){
     if (bookmarkImg.src.includes('1.jpg')) {
    bookmarkImg.src = 'icons/2.jpg';
} else {
    bookmarkImg.src = 'icons/1.jpg';
}
}
    });

        // 8. Assemble DOM Tree
        verticle.appendChild(titleDiv);
        verticle.appendChild(authorDiv);
        verticle.appendChild(summaryDiv);

        // Group the buttons side-by-side
        actionsGroup.appendChild(likeBtn);
        actionsGroup.appendChild(bookmarkBtn);

        // Add metadata and buttons to the single horizontal row
        footerRow.appendChild(dateDiv);
        footerRow.appendChild(categoryDiv);
        footerRow.appendChild(actionsGroup);
        
        verticle.appendChild(footerRow);

        itemDiv.appendChild(pict);
        itemDiv.appendChild(verticle);
        
        container.appendChild(itemDiv);
    });
}



const searchQueries = {
    "All": "artificial intelligence",
    "Artificial Intelligence": "artificial intelligence",
    "Robotics": "robotics",
    "Cybersecurity": "cybersecurity",
    "Quantum Computing": "quantum computing",
    "Software": "software engineering",
    "Energy Tech": "renewable energy"
};


function fetchArticles(category) {
    let url="http://127.0.0.1:8000/articles/live";
    const query = searchQueries[category];

if (category !== "All") {
    url = `http://127.0.0.1:8000/articles/live?query=${encodeURIComponent(query)}`;
} 
fetch(url)
    .then(res => res.json())
    .then(data =>renderCharacters(data))
    .catch(error => console.error('Error fetching data:', error));
}

function onCategoryClick(category){
    sessionStorage.setItem("category",category);
    fetchArticles(category);
}

document.addEventListener("DOMContentLoaded",()=>{
    const savedCategory=sessionStorage.getItem("category");
    const dropdown=document.getElementById("categoryselect");
    if(savedCategory){
        dropdown.value=savedCategory;
        fetchArticles(savedCategory);
    }else{
        fetchArticles("All");
    }
});





