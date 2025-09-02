function renderRoomPriceChart(data, chartId) {
    // 初始化ECharts实例
    var chartDom = document.getElementById(chartId);
    var myChart = echarts.init(chartDom);
    
    // 判断是否为全屏模式
    var isFullscreen = chartId === 'fullscreen-chart';
    
    // 图表配置项
    var option = {
        title: {
            text: '户型价格走势',
            left: 'center',
            textStyle: {
                fontSize: isFullscreen ? 20 : 14
            }
        },
        tooltip: {
            trigger: 'axis',
            formatter: function(params) {
                return params[0].name + '<br/>' + params[0].seriesName + ': ' + params[0].value + '元/月';
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
            type: 'category',
            data: data.room_types,
            axisLabel: {
                interval: 0,
                fontSize: isFullscreen ? 14 : 12
            },
            axisLine: {
                lineStyle: {
                    color: '#333'
                }
            },
            axisTick: {
                alignWithLabel: true
            }
        },
        yAxis: {
            type: 'value',
            name: '平均价格（元/月）',
            nameTextStyle: {
                fontSize: isFullscreen ? 14 : 12
            },
            axisLabel: {
                fontSize: isFullscreen ? 14 : 12
            },
            splitLine: {
                lineStyle: {
                    type: 'dashed'
                }
            }
        },
        series: [
            {
                name: '平均价格',
                type: 'line',
                data: data.avg_prices,
                smooth: true,
                symbol: 'circle',
                symbolSize: isFullscreen ? 10 : 8,
                itemStyle: {
                    color: '#e74c3c'
                },
                lineStyle: {
                    width: isFullscreen ? 3 : 2,
                    color: '#e74c3c'
                },
                areaStyle: {
                    color: {
                        type: 'linear',
                        x: 0,
                        y: 0,
                        x2: 0,
                        y2: 1,
                        colorStops: [
                            {
                                offset: 0,
                                color: 'rgba(231, 76, 60, 0.3)'
                            },
                            {
                                offset: 1,
                                color: 'rgba(231, 76, 60, 0.1)'
                            }
                        ]
                    }
                },
                label: isFullscreen ? {
                    show: true,
                    position: 'top',
                    formatter: '{c}元/月',
                    fontSize: 14
                } : undefined,
                markPoint: isFullscreen ? {
                    data: [
                        { type: 'max', name: '最高价格' },
                        { type: 'min', name: '最低价格' }
                    ]
                } : undefined,
                markLine: isFullscreen ? {
                    data: [
                        { type: 'average', name: '平均价格' }
                    ],
                    label: {
                        formatter: '平均: {c}元/月'
                    }
                } : undefined
            }
        ],
        // 全屏模式下添加工具栏
        toolbox: isFullscreen ? {
            feature: {
                dataZoom: {
                    yAxisIndex: 'none'
                },
                magicType: {
                    type: ['line', 'bar']
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