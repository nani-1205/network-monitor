document.addEventListener('DOMContentLoaded', function() {
    const hostListDiv = document.getElementById('host-list');
    const refreshBtn = document.getElementById('refresh-btn');
    const showAllBtn = document.getElementById('show-all-btn');
    const chartDom = document.getElementById('sankey-chart');
    const myChart = echarts.init(chartDom);
    
    let currentFocusIP = null;

    function isWellKnownPort(port) {
        const knownPorts = [80, 443, 22, 21, 25, 53, 110, 143, 3306, 5432, 9418];
        return knownPorts.includes(port);
    }

    async function loadHosts() {
        try {
            const response = await fetch('/api/hosts');
            if (!response.ok) throw new Error('Failed to fetch hosts');
            const hosts = await response.json();
            
            hostListDiv.innerHTML = '';
            hosts.forEach(ip => {
                const item = document.createElement('div');
                item.className = 'host-item';
                item.innerHTML = `<label class="host-label" data-ip="${ip}">${ip}</label>`;
                hostListDiv.appendChild(item);
            });

            document.querySelectorAll('.host-label').forEach(label => {
                label.addEventListener('click', (event) => {
                    const ip = event.target.dataset.ip;
                    document.querySelectorAll('.host-label.active').forEach(l => l.classList.remove('active'));
                    event.target.classList.add('active');
                    currentFocusIP = ip;
                    showAllBtn.style.display = 'inline-block';
                    fetchAndDrawChart();
                });
            });
        } catch (error) {
            console.error('Error loading hosts:', error);
        }
    }

    async function fetchAndDrawChart() {
        myChart.showLoading();
        showAllBtn.style.display = currentFocusIP ? 'inline-block' : 'none';
        
        const params = new URLSearchParams();
        if (currentFocusIP) params.append('focus_ip', currentFocusIP);

        try {
            const response = await fetch(`/api/traffic_data?${params.toString()}`);
            if (!response.ok) throw new Error('Failed to fetch traffic data');
            
            const data = await response.json();
            
            if (!data.nodes || data.nodes.length === 0) {
                myChart.hideLoading();
                myChart.clear();
                return;
            }
            
            // --- Advanced Coloring ---
            const internalColor = '#00e5ff'; // Blue/Teal for Internal
            const externalColor = '#64ffda'; // Green for External
            
            data.nodes.forEach(node => {
                node.itemStyle = { color: node.depth === 0 ? internalColor : externalColor };
            });

            data.links.forEach(link => {
                // Default style for "normal" traffic
                link.lineStyle = { color: 'source', opacity: 0.4, curveness: 0.5 };
                
                // Highlight potentially suspicious traffic
                const isSuspicious = link.ports.length > 0 && !link.ports.some(isWellKnownPort);
                if (isSuspicious) {
                    link.lineStyle.color = '#ff4b5c'; // Red for suspicious
                    link.lineStyle.opacity = 0.7;
                }
            });

            const chartOption = {
                title: { text: currentFocusIP ? `Traffic for ${currentFocusIP}` : 'Network Traffic Flow', textStyle: { color: '#cdd6f4', fontWeight: 'normal' } },
                tooltip: {
                    trigger: 'item', triggerOn: 'mousemove',
                    formatter: (params) => {
                        if (params.dataType === 'edge') {
                            const ports = params.data.ports.length > 0 ? params.data.ports.slice(0, 5).join(', ') + (params.data.ports.length > 5 ? '...' : '') : 'N/A';
                            return `<b>${params.data.source} → ${params.data.target}</b><br/>Data: ${(params.data.value / 1024).toFixed(2)} KB<br/>Ports: ${ports}`;
                        }
                        return `<b>${params.name}</b>`;
                    }
                },
                series: [{
                    type: 'sankey',
                    data: data.nodes,
                    links: data.links,
                    orient: 'horizontal',
                    draggable: true,
                    focusNodeAdjacency: 'allEdges',
                    nodeWidth: 20,
                    nodeGap: 12,
                    label: {
                        color: '#cdd6f4',
                        position: 'right',
                        formatter: (params) => params.name // Always show label
                    },
                    levels: [{
                        depth: 0,
                        label: { position: 'right' },
                        itemStyle: { color: internalColor }
                    }, {
                        depth: 1,
                        label: { position: 'left' },
                        itemStyle: { color: externalColor }
                    }],
                    lineStyle: { curveness: 0.5 }
                }]
            };
            
            myChart.hideLoading();
            myChart.setOption(chartOption, true);

        } catch (error) {
            console.error('Error fetching/drawing chart:', error);
            myChart.hideLoading();
        }
    }

    refreshBtn.addEventListener('click', fetchAndDrawChart);
    showAllBtn.addEventListener('click', () => {
        currentFocusIP = null;
        document.querySelectorAll('.host-label.active').forEach(l => l.classList.remove('active'));
        fetchAndDrawChart();
    });

    loadHosts().then(fetchAndDrawChart);
    window.addEventListener('resize', () => myChart.resize());
});