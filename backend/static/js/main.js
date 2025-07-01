document.addEventListener('DOMContentLoaded', function() {
    const hostListDiv = document.getElementById('host-list');
    const refreshBtn = document.getElementById('refresh-btn');
    const showAllBtn = document.getElementById('show-all-btn');
    const loadingMessage = document.getElementById('loading-message');

    const chartDom = document.getElementById('sankey-chart');
    const myChart = echarts.init(chartDom);
    let chartOption;
    let currentFocusIP = null;

    async function loadHosts() {
        try {
            const response = await fetch('/api/hosts');
            if (!response.ok) throw new Error('Failed to fetch hosts');
            const hosts = await response.json();
            
            hostListDiv.innerHTML = '';
            if (hosts.length === 0) {
                hostListDiv.innerHTML = '<p>No hosts detected yet.</p>';
                return;
            }

            hosts.forEach(ip => {
                const item = document.createElement('div');
                item.className = 'host-item';
                
                item.innerHTML = `
                    <input type="checkbox" id="host-cb-${ip}" data-ip="${ip}" name="server" value="${ip}">
                    <label class="host-label" for="host-cb-${ip}" data-ip="${ip}">${ip}</label>
                `;
                hostListDiv.appendChild(item);
            });

            document.querySelectorAll('input[name="server"]').forEach(checkbox => {
                checkbox.addEventListener('change', () => fetchAndDrawChart());
            });

            document.querySelectorAll('.host-label').forEach(label => {
                label.addEventListener('click', (event) => {
                    event.preventDefault();
                    const ip = event.target.dataset.ip;
                    
                    document.querySelectorAll('.host-label.active').forEach(l => l.classList.remove('active'));
                    event.target.classList.add('active');

                    currentFocusIP = ip;
                    showAllBtn.classList.remove('hidden');
                    fetchAndDrawChart();
                });
            });

        } catch (error) {
            console.error('Error loading hosts:', error);
            hostListDiv.innerHTML = '<p style="color: #f44336;">Error loading hosts.</p>';
        }
    }

    async function fetchAndDrawChart() {
        loadingMessage.classList.remove('hidden');
        myChart.showLoading();

        const serverCheckboxes = document.querySelectorAll('input[name="server"]:checked');
        const serverIPs = Array.from(serverCheckboxes).map(cb => cb.value);
        
        const params = new URLSearchParams();
        serverIPs.forEach(ip => params.append('servers[]', ip));

        if (currentFocusIP) {
            params.append('focus_ip', currentFocusIP);
        }

        try {
            const response = await fetch(`/api/traffic_data?${params.toString()}`);
            if (!response.ok) throw new Error('Failed to fetch traffic data');
            
            let data = await response.json();
            
            if (!data.nodes || data.nodes.length === 0) {
                myChart.hideLoading();
                loadingMessage.classList.add('hidden');
                myChart.clear();
                myChart.setOption({
                    title: { text: currentFocusIP ? `No traffic data for ${currentFocusIP}` : 'No Traffic Data Available',
                        subtext: 'Try selecting another host or showing all traffic.', left: 'center', top: 'center', textStyle: { color: '#cdd6f4' }
                    }
                });
                return;
            }

            const clientColor = '#00e5ff'; 
            const serverColor = '#ff4b5c';
            data.nodes.forEach(node => {
                node.itemStyle = { color: node.name.startsWith('[S]') ? serverColor : clientColor };
                node.name = node.name.replace(/\[C\] |\[S\] /g, '');
            });
             data.links.forEach(link => {
                link.source = link.source.replace(/\[C\] |\[S\] /g, '');
                link.target = link.target.replace(/\[C\] |\[S\] /g, '');
            });

            chartOption = {
                title: { text: currentFocusIP ? `Traffic for ${currentFocusIP}` : 'LAN Traffic Flow', textStyle: { color: '#cdd6f4' } },
                tooltip: {
                    trigger: 'item',
                    triggerOn: 'mousemove',
                    formatter: function (params) {
                        if (params.dataType === 'edge') {
                            let portText = '';
                            if (params.data.ports && params.data.ports.length > 0) {
                                const portsToShow = params.data.ports.slice(0, 5).join(', ');
                                const moreText = params.data.ports.length > 5 ? '...' : '';
                                portText = `Ports: <strong>${portsToShow}${moreText}</strong><br/>`;
                            }
                            return `${params.data.source} → ${params.data.target}<br/>` +
                                   `Protocol(s): <strong>${params.data.protocol}</strong><br/>` +
                                   portText +
                                   `Data: <strong>${(params.data.value / 1024).toFixed(2)} KB</strong>`;
                        }
                        return `Host: <strong>${params.name}</strong>`;
                    }
                },
                series: [ {
                        type: 'sankey', data: data.nodes, links: data.links,
                        layout: 'none', orient: 'horizontal', draggable: true,
                        focusNodeAdjacency: 'allEdges', nodeGap: 18,
                        label: { color: '#fff', position: 'right',
                            formatter: function (params) { if (params.value > 10000) { return params.name; } return params.name; }
                        },
                        lineStyle: { color: 'gradient', curveness: 0.5, opacity: 0.6 },
                        itemStyle: { borderWidth: 1, borderColor: '#313a50' },
                    } ]
            };
            
            myChart.hideLoading();
            loadingMessage.classList.add('hidden');
            myChart.setOption(chartOption, true);

        } catch (error) {
            console.error('Error fetching/drawing chart:', error);
            myChart.hideLoading();
            loadingMessage.classList.remove('hidden');
            loadingMessage.textContent = 'Error loading chart data. Please check the console and ensure the backend is running.';
        }
    }

    refreshBtn.addEventListener('click', () => {
        fetchAndDrawChart();
    });

    showAllBtn.addEventListener('click', () => {
        currentFocusIP = null;
        showAllBtn.classList.add('hidden');
        document.querySelectorAll('.host-label.active').forEach(l => l.classList.remove('active'));
        fetchAndDrawChart();
    });

    loadHosts().then(() => fetchAndDrawChart());
    
    window.addEventListener('resize', () => { myChart.resize(); });
});