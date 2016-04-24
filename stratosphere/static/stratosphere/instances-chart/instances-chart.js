var drawInstancesChart = function(data) {
    var series = [{
        data: [],
        label: "Running",
        color: "#5cb85c",
    },
    {
        data: [],
        label: "Pending",
        color: "#f0ad4e",
    },
    {
        data: [],
        label: "Failed",
        color: "#d9534f",
    }];

    for (var i = 0; i < data.length; i += 1) {
        var snapshot = data[i];
        series[0].data.push([snapshot.time, snapshot.running]);
    }

    for (var i = 0; i < data.length; i += 1) {
        var snapshot = data[i];
        series[1].data.push([snapshot.time, snapshot.pending]);
    }

    for (var i = 0; i < data.length; i += 1) {
        var snapshot = data[i];
        series[2].data.push([snapshot.time, snapshot.failed]);
    }

    // extend last value to edge of graph, or it'll end in a vertical line
    var now = new Date().getTime();
    if (data.length > 0) {
        var last_snapshot = data[data.length-1];
        series[0].data.push([now, last_snapshot.running]);
        series[1].data.push([now, last_snapshot.pending]);
        series[2].data.push([now, snapshot.failed]);
    }

    if ($('#instances-chart').length) {
        var slider = $('#instances-chart-range-slider');
        var current_range = slider.val();

        var current_min = parseInt(current_range[0]);
        var current_max = parseInt(current_range[1]);

        var xmin = (current_min == 0 || changed_instances_chart_range_limit) && data.length ? data[0].time : current_min;
        var xmax = null;
        if (current_min == 0 || changed_instances_chart_range_limit || current_max == window.last_now)
            xmax = now;
        else
            xmax = current_max;

        changed_instances_chart_range_limit = false;
        window.last_now = now;

        window.instances_chart_plot = $("#instances-chart").plot(series, {
            xaxis: {
                mode: "time",
                tickLength: 0,
                timezone: "browser",
                twelveHourClock: true,
                min: xmin,
                max: xmax,
                autoscaleMargin: 0.0,
            },
            yaxis: {
                tickLength: 0,
                tickDecimals: 0,
                autoscaleMargin: 0.0,
            },
            series: {
                stack: true,
                lines: {
                    show: true,
                    fill: true,
                    steps: true,
                },
            },
            legend: {
                position: 'nw',
            },
            grid: {
                borderWidth: 0,
                minBorderMargin: 0,
                margin: 0,
            },
        }).data('plot');

        if (data.length)
            slider.noUiSlider({range: {min: data[0].time, max: now}, start: [xmin, xmax]}, true);
    }
}

function getStateHistory(cb) {
    $.get('/compute/state_history/', {limit: instances_chart_range_limit}).done(cb);
}

function setUpSlider() {
    var slider = $("#instances-chart-range-slider");

    slider.noUiSlider({
        start: [0, 10],
        behaviour: 'drag',
        connect: true,
        //step: 1, // force integer values
        range: {
            'min':  0,
            'max':  10,
        },
    });

    slider.on('slide', function(event, value) {
        instances_chart_range_slider_moving = true;
        instances_chart_plot.getOptions().xaxes[0].min = parseInt(value[0]);
        instances_chart_plot.getOptions().xaxes[0].max = parseInt(value[1]);
        instances_chart_plot.setupGrid();
        instances_chart_plot.draw();
    }).on('set', function() {
        instances_chart_range_slider_moving = false;
    });
}

function selectedInstancesChartRangeButton() {
    return $('#instances-chart-max-range-buttons button.btn-info');
}

$(document).ready(function() {
    instances_chart_range_limit = selectedInstancesChartRangeButton().attr('seconds') || null;
    changed_instances_chart_range_limit = false;
    instances_chart_range_slider_moving = false;

    setUpSlider();

    $('#instances-chart-max-range-buttons button').click(function() {
        var oldSelectedButton = selectedInstancesChartRangeButton();
        oldSelectedButton.removeClass('btn-info').addClass('btn-default');

        var newSelectedButton = $(this);
        newSelectedButton.removeClass('btn-default').addClass('btn-info');
        instances_chart_range_limit = $(this).attr('seconds') || null;

        getStateHistory(function (data) {
            changed_instances_chart_range_limit = true;
            drawInstancesChart(data);
        });
    });

    getStateHistory(function (data) {
        drawInstancesChart(data);
    });

    setInterval(function() {
        getStateHistory(function (data) {
            if (!instances_chart_range_slider_moving)
                drawInstancesChart(data);
        });
    }, 3000);
});