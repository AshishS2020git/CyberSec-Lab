window.addEventListener("DOMContentLoaded", () => {

    let online = 0;

    document.querySelectorAll(".badge.online").forEach(() => {

        online++;

    });

    const counter = document.getElementById("onlineCount");

    if(counter){

        counter.innerText = online;

    }

});

async function checkRefresh() {

    const response = await fetch("/refresh_flag");
    const data = await response.json();

    if (data.refresh) {
        location.reload();
    }
}

setInterval(checkRefresh, 2000);