function toggleEvents() {
    const el = document.getElementById("event-list");
    if (el.style.display === "none") {
        el.style.display = "block";
    } else {
        el.style.display = "none";
    }
}