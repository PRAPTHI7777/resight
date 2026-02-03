//Fetch data from local JSON file and render it to HTML document by using Vanilla JavaScript
const container=document.querySelector('.contain');

function renderCharacters(data){
    container.innerHTML='';
    data.forEach(item => {
        const itemDiv=document.createElement('div');
        const pict=document.createElement('div');
        const verticle=document.createElement('div');
        const titleDiv=document.createElement('div');
        const authorDiv=document.createElement('div');
        const summaryDiv=document.createElement('div');
        const dateDiv=document.createElement('div');
        const categoryDiv=document.createElement('div');
        itemDiv.className='container';
        pict.className='picture';
        verticle.className='verticalcontain';
        titleDiv.className='title';
        authorDiv.className='authors';
        summaryDiv.className='summary';
        dateDiv.className='date';
        categoryDiv.className='category';
        titleDiv.textContent=item.title;
        authorDiv.textContent='- '+item.authors.join(', ');
        summaryDiv.textContent=item.description;
        dateDiv.textContent=item.date;
        categoryDiv.textContent=item.category;
        itemDiv.appendChild(pict);
        itemDiv.appendChild(verticle);
        verticle.appendChild(titleDiv);
        verticle.appendChild(authorDiv);
        verticle.appendChild(summaryDiv);
        verticle.appendChild(dateDiv);
        dateDiv.appendChild(categoryDiv);
        container.appendChild(itemDiv);

});
}

function fetchArticles(category) {
    let url="http://127.0.0.1:8000/articles";
    if(category!="All"){
        url=`http://127.0.0.1:8000/articles/category/${category}`;
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
    if(savedCategory){
        fetchArticles(savedCategory);
    }else{
        fetchArticles("All");
    }

});




