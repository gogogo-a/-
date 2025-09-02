function renderRoomTypeChart(data, chartId) {
    // 初始化ECharts实例
    var chartDom = document.getElementById(chartId);
    var myChart = echarts.init(chartDom);
    
    // 判断是否为全屏模式
    var isFullscreen = chartId === 'fullscreen-chart';
    
    // 图表配置项
    var option = {
        title: {
            text: '户型占比分布',
            left: 'center',
            textStyle: {
                fontSize: isFullscreen ? 20 : 14
            }
        },
        tooltip: {
            trigger: 'item',
            formatter: '{b}: {c}套 ({d}%)'
        },
        legend: {
            orient: 'horizontal',
            bottom: isFullscreen ? 20 : 10,
            textStyle: {
                fontSize: isFullscreen ? 14 : 12
            },
            type: isFullscreen ? 'scroll' : 'plain'
        },
        series: [
            {
                name: '户型占比',
                type: 'pie',
                radius: isFullscreen ? '55%' : '50%',
                center: ['50%', '50%'],
                data: data,
                emphasis: {
                    itemStyle: {
                        shadowBlur: 10,
                        shadowOffsetX: 0,
                        shadowColor: 'rgba(0, 0, 0, 0.5)'
                    }
                },
                label: {
                    formatter: isFullscreen ? '{b}: {c}套 ({d}%)' : '{b}: {d}%',
                    fontSize: isFullscreen ? 14 : 12
                },
                labelLine: {
                    smooth: true,
                    length: isFullscreen ? 10 : 5,
                    length2: isFullscreen ? 20 : 10
                },
                itemStyle: {
                    borderRadius: 5,
                    borderColor: '#fff',
                    borderWidth: 2
                },
                animationType: 'scale',
                animationEasing: 'elasticOut'
            }
        ],
        // 全屏模式下添加工具栏
        toolbox: isFullscreen ? {
            feature: {
                saveAsImage: {},
                dataView: {
                    readOnly: true,
                    title: '数据视图'
                }
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