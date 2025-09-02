function renderPriceTrendChart(data, chartId) {
    // 初始化ECharts实例
    var chartDom = document.getElementById(chartId);
    var myChart = echarts.init(chartDom);
    
    // 判断是否为全屏模式
    var isFullscreen = chartId === 'fullscreen-chart';
    
    // 图表配置项
    var option = {
        title: {
            text: '房价走势预测',
            left: 'center',
            textStyle: {
                fontSize: isFullscreen ? 20 : 14
            }
        },
        tooltip: {
            trigger: 'axis',
            axisPointer: {
                type: 'cross'
            },
            formatter: function(params) {
                var result = params[0].name + ' 平方米<br/>';
                params.forEach(function(param) {
                    result += param.seriesName + ': ' + param.value[1] + ' 元/月<br/>';
                });
                return result;
            }
        },
        legend: {
            data: ['实际价格', '预测价格'],
            bottom: isFullscreen ? 20 : 10,
            textStyle: {
                fontSize: isFullscreen ? 14 : 12
            }
        },
        grid: {
            left: isFullscreen ? '5%' : '3%',
            right: isFullscreen ? '5%' : '4%',
            bottom: isFullscreen ? '15%' : '20%',
            top: isFullscreen ? '15%' : '20%',
            containLabel: true
        },
        xAxis: {
            type: 'value',
            name: '面积（平方米）',
            nameLocation: 'middle',
            nameGap: isFullscreen ? 40 : 30,
            axisLabel: {
                formatter: '{value} m²',
                fontSize: isFullscreen ? 14 : 12
            },
            nameTextStyle: {
                fontSize: isFullscreen ? 16 : 12
            }
        },
        yAxis: {
            type: 'value',
            name: '价格（元/月）',
            nameLocation: 'middle',
            nameGap: isFullscreen ? 60 : 50,
            axisLabel: {
                fontSize: isFullscreen ? 14 : 12
            },
            nameTextStyle: {
                fontSize: isFullscreen ? 16 : 12
            }
        },
        series: [
            {
                name: '实际价格',
                type: 'scatter',
                data: data.actual.x.map((x, index) => [x, data.actual.y[index]]),
                symbolSize: isFullscreen ? 10 : 8,
                itemStyle: {
                    color: '#3498db'
                },
                emphasis: {
                    itemStyle: {
                        shadowBlur: 10,
                        shadowColor: 'rgba(0, 0, 0, 0.5)'
                    }
                }
            },
            {
                name: '预测价格',
                type: 'line',
                smooth: true,
                data: data.predicted.x.map((x, index) => [x, data.predicted.y[index]]),
                itemStyle: {
                    color: '#e74c3c'
                },
                lineStyle: {
                    width: isFullscreen ? 3 : 2
                }
            }
        ],
        // 全屏模式下添加工具栏
        toolbox: isFullscreen ? {
            feature: {
                dataZoom: {
                    yAxisIndex: 'none'
                },
                restore: {},
                saveAsImage: {}
            },
            right: 20,
            top: 20
        } : undefined
    };
    
    // 使用配置项显示图表
    myChart.setOption(option);
    
    // 窗口大小变化时，重新调整图表大小
    window.addEventListener('resize', function() {
        myChart.resize();
    });
} 