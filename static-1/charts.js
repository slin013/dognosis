let ctx = document.getElementById("hrChart").getContext("2d");

let hrChart = new Chart(ctx, {
    type: "line",
    data: {
        labels: [],
        datasets: [{
            label: "Heart Rate",
            data: [],
            borderWidth: 2
        }]
    }
});

async function updateChart(){

    const response = await fetch("/live-data");
    const data = await response.json();

    const timestamps = data.map(x => new Date(x.timestamp*1000).toLocaleTimeString());
    const heartRates = data.map(x => x.heart_rate);

    hrChart.data.labels = timestamps.reverse();
    hrChart.data.datasets[0].data = heartRates.reverse();

    hrChart.update();
}

setInterval(updateChart,3000);
updateChart();