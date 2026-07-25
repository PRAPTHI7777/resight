const paper = JSON.parse(
    sessionStorage.getItem("selectedPaper")
);

document.getElementById("title").textContent =
paper.title;

document.getElementById("authors").textContent =
paper.authors.join(", ");

document.getElementById("date").textContent =
paper.date;

document.getElementById("category").textContent =
paper.category;

document.getElementById("description").textContent =
paper.description;

document.getElementById("paperLink").href =
paper.link;