document.addEventListener('DOMContentLoaded', function() {
    const hostListDiv = document.getElementById('host-list');
    const refreshBtn = document.getElementById('refresh-btn');
    const loadingMessage = document.getElementById('loading-message');

    // Initialize ECharts instance
    const chartDom = document.getElementById('sankey-chart');
    const myChart = echarts.init(chartDom);
    let chartOption;

    // --- Core Functions ---

    /**
     * Fetches all unique hosts from the backend and populates the sidebar.
     */
    async function loadHosts() {
        try {
            const response = await fetch('/api/hosts');
            if (!response.ok) throw new Error('Failed to fetch hosts');
            const hosts = await response.json();
            
            hostListDiv.innerHTML = ''; // Clear previous list
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

            // Add event listeners to checkboxes to trigger a chart refresh on change
            document.querySelectorAll('input[name="server"]').forEach(checkbox => {
                checkbox.addEventListener('change', fetchAndDrawChart);
            });

        } catch (error) {
            console.error('Error loading hosts:', error);
            hostListDiv.innerHTML = '<p style="color: #f44336;">Error loading hosts.</p>';
        }
    }

    /**
     * Fetches traffic data and renders the Sankey chart.
     */
    async function fetchAndDrawChart() {
        loadingMessage.classList.remove('hidden');
        myChart.showLoading();

        // Get the list of IPs marked as servers
        const serverCheckboxes = document.querySelectorAll('input[name="server"]:checked');
        const serverIPs = Array.from(serverCheckboxes).map(cb => cb.value);
        const serverParams = new URLSearchParams();
        serverIPs.forEach(ip => serverParams.append('servers[]', ip));

        try {
            const response = await fetch(`/api/traffic_data?${serverParams.toString()}`);
            if (!response.ok) throw new Error('Failed to fetch traffic data');
            
            const data = await response.json();
            
            if (data.nodes.length === 0) {
                myChart.hideLoading();
                loadingMessage.classList.add('hidden');
                 myChart.clear(); // Clear previous chart
                // Display a message in the chart area
                myChart.setOption({
                    title: {
                        text: 'No Traffic Data Available',
                        subtext: 'Please wait for the capture script to log some network activity.',
                        left: 'center',
                        top: 'center',
                        textStyle: {
                            color: '#cdd6f4'
                        }
                    }
                });
                return;
            }

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
                            // Tooltip for links (edges)
                            return `${params.data.source.replace(/\[C\] |\[S\] /g, '')} → ${params.data.target.replace(/\[C\] |\[S\] /g, '')}<br/>` +
                                   `Protocol: <strong>${params.data.protocol}</strong><br/>` +
                                   `Data: <strong>${(params.data.value / 1024).toFixed(2)} KB</strong>`;
                        }
                        // Tooltip for nodes
                        return `Host: <strong>${params.name.replace(/\[C\] |\[S\] /g, '')}</strong>`;
                    }
                },
                series: [
                    {
                        type: 'sankey',
                        layout: 'none',
                        emphasis: {
                            focus: 'adjacency'
                        },
                        data: data.nodes,
                        links: data.links,
                        // Styling inspired by the video
                        lineStyle: {
                            color: 'source',
                            curveness: 0.5,
                            opacity: 0.6
                        },
                        label: {
                            color: '#cdd6f4',
                            fontFamily: 'Roboto, sans-serif'
                        },
                        nodeAlign: 'justify', // Aligns nodes vertically
                        itemStyle: {
                            color: '#00e5ff', // Default node color
                            borderColor: '#00e5ff'
                        },
                    }
                ]
            };
            
            myChart.hideLoading();
            loadingMessage.classList.add('hidden');
            myChart.setOption(chartOption);

        } catch (error) {
            console.error('Error fetching/drawing chart:', error);
            myChart.hideLoading();
            loadingMessage.classList.remove('hidden');
            loadingMessage.textContent = 'Error loading chart data. Please check the console and ensure the backend is running.';
        }
    }

    // --- Initial Load ---
    refreshBtn.addEventListener('click', () => {
        loadHosts();
        fetchAndDrawChart();
    });

    // Initial data load on page start
    loadHosts();
    fetchAndDrawChart();
    
    // Make chart responsive
    window.addEventListener('resize', () => {
        myChart.resize();
    });
});