function renderCommunityChart(data, chartId) {
    // 初始化ECharts实例
    var chartDom = document.getElementById(chartId);
    var myChart = echarts.init(chartDom);
    
    // 判断是否为全屏模式
    var isFullscreen = chartId === 'fullscreen-chart';
    
    // 图表配置项
    var option = {
        title: {
            text: '小区房源数量TOP20',
            left: 'center',
            textStyle: {
                fontSize: isFullscreen ? 20 : 14
            }
        },
        tooltip: {
            trigger: 'axis',
            axisPointer: {
                type: 'shadow'
            },
            formatter: function(params) {
                return params[0].name + '<br/>' + params[0].seriesName + ': ' + params[0].value + '套';
            }
        },
        grid: {
            left: isFullscreen ? '5%' : '3%',
            right: isFullscreen ? '5%' : '4%',
            bottom: isFullscreen ? '15%' : '25%',
            containLabel: true
        },
        xAxis: {
            type: 'category',
            data: data.addresses,
            axisLabel: {
                interval: 0,
                rotate: isFullscreen ? 30 : 45,
                textStyle: {
                    fontSize: isFullscreen ? 12 : 10
                },
                formatter: function(value) {
                    // 如果是全屏模式，显示完整名称，否则截断
                    if (isFullscreen) {
                        return value;
                    } else {
                        if (value.length > 6) {
                            return value.substring(0, 6) + '...';
                        }
                        return value;
                    }
                }
            }
        },
        yAxis: {
            type: 'value',
            name: '房源数量',
            nameTextStyle: {
                fontSize: isFullscreen ? 14 : 12
            },
            axisLabel: {
                fontSize: isFullscreen ? 12 : 10
            }
        },
        series: [
            {
                name: '房源数量',
                type: 'bar',
                data: data.counts,
                itemStyle: {
                    color: function(params) {
                        // 生成渐变色
                        var colorList = ['#83bff6', '#188df0', '#188df0', '#83bff6'];
                        var index = params.dataIndex % colorList.length;
                        return colorList[index];
                    }
                },
                emphasis: {
                    itemStyle: {
                        color: '#2980b9'
                    }
                },
                barWidth: isFullscreen ? '60%' : '70%',
                label: isFullscreen ? {
                    show: true,
                    position: 'top',
                    formatter: '{c}套'
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
        } : undefined,
        // 全屏模式下添加数据缩放
        dataZoom: isFullscreen ? [
            {
                type: 'slider',
                show: true,
                xAxisIndex: [0],
                start: 0,
                end: 100
            }
        ] : undefined
    };
    
    // 使用配置项显示图表
    myChart.setOption(option);
    
    // 窗口大小变化时，重新调整图表大小
    window.addEventListener('resize', function() {
        myChart.resize();
    });
} 