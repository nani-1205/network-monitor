document.addEventListener('DOMContentLoaded', function() {
    const hostListDiv = document.getElementById('host-list');
    const refreshBtn = document.getElementById('refresh-btn');
    const loadingMessage = document.getElementById('loading-message');

    const chartDom = document.getElementById('sankey-chart');
    const myChart = echarts.init(chartDom);
    let chartOption;

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
                    <input type="checkbox" id="host-${ip}" name="server" value="${ip}">
                    <label for="host-${ip}">${ip}</label>
                `;
                hostListDiv.appendChild(item);
            });

            document.querySelectorAll('input[name="server"]').forEach(checkbox => {
                checkbox.addEventListener('change', fetchAndDrawChart);
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
        const serverParams = new URLSearchParams();
        serverIPs.forEach(ip => serverParams.append('servers[]', ip));

        try {
            const response = await fetch(`/api/traffic_data?${serverParams.toString()}`);
            if (!response.ok) throw new Error('Failed to fetch traffic data');
            
            let data = await response.json();
            
            if (!data.nodes || data.nodes.length === 0) {
                myChart.hideLoading();
                loadingMessage.classList.add('hidden');
                myChart.clear();
                myChart.setOption({
                    title: {
                        text: 'No Traffic Data Available',
                        subtext: 'Please wait for the capture script to log some network activity.',
                        left: 'center',
                        top: 'center',
                        textStyle: { color: '#cdd6f4' }
                    }
                });
                return;
            }

            const clientColor = '#00e5ff';
            const serverColor = '#ff4b5c';
            data.nodes.forEach(node => {
                node.itemStyle = {
                    color: node.name.startsWith('[S]') ? serverColor : clientColor
                };
                // Remove the prefix for cleaner display
                node.name = node.name.replace(/\[C\] |\[S\] /g, '');
            });
            // Also clean up link names
             data.links.forEach(link => {
                link.source = link.source.replace(/\[C\] |\[S\] /g, '');
                link.target = link.target.replace(/\[C\] |\[S\] /g, '');
            });


            chartOption = {
                title: {
                    text: 'LAN Traffic Flow',
                    textStyle: { color: '#cdd6f4' }
                },
                tooltip: {
                    trigger: 'item',
                    triggerOn: 'mousemove',
                    formatter: function (params) {
                         if (params.dataType === 'edge') {
                            return `${params.data.source} → ${params.data.target}<br/>` +
                                   `Protocol(s): <strong>${params.data.protocol}</strong><br/>` +
                                   `Data: <strong>${(params.data.value / 1024).toFixed(2)} KB</strong>`;
                        }
                        return `Host: <strong>${params.name}</strong>`;
                    }
                },
                series: [
                    {
                        type: 'sankey',
                        data: data.nodes,
                        links: data.links,
                        
                        // ++++++++ GOOD VIEW CONFIGURATION ++++++++
                        layout: 'none',       // Use the standard layout
                        orient: 'horizontal', // Revert to left-to-right
                        draggable: true,      // Allow user to drag nodes
                        focusNodeAdjacency: 'allEdges', // Highlight all related nodes/links on hover
                        
                        // Increase vertical spacing between nodes
                        nodeGap: 18,

                        label: {
                            color: '#fff',
                            // Smartly position labels inside or outside
                            position: 'right', 
                            formatter: function (params) {
                                // For large nodes, show label inside to save space
                                if (params.value > 10000) { // Adjust this threshold as needed
                                    return params.name;
                                }
                                return params.name;
                            }
                        },
                        // +++++++++++++++++++++++++++++++++++++++++++

                        lineStyle: { color: 'gradient', curveness: 0.5, opacity: 0.6 },
                        itemStyle: { borderWidth: 1, borderColor: '#313a50' },
                    }
                ]
            };
            
            myChart.hideLoading();
            loadingMessage.classList.add('hidden');
            myChart.setOption(chartOption, true);

        } catch (error) {
            console.error('Error fetching/drawing chart:', error);
            myChart.hideLoading();
            loadingMessage.classList.add('hidden');
            loadingMessage.textContent = 'Error loading chart data. Please check the console and ensure the backend is running.';
        }
    }

    refreshBtn.addEventListener('click', () => {
        fetchAndDrawChart();
    });

    loadHosts().then(fetchAndDrawChart);
    
    window.addEventListener('resize', () => {
        myChart.resize();
    });
});