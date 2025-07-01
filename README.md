# LAN Network Analytics Monitor

This project is a web-based network monitoring tool inspired by advanced cybersecurity dashboards. It uses a two-part architecture to safely and effectively capture and visualize network traffic on a local network.

## Architecture

1.  **Packet Capture Script (`packet_capture.py`)**:
    *   A Python script using `scapy` to capture live network packets.
    *   **Requires root/administrator privileges** to run (`sudo python ...`).
    *   It analyzes packets to identify source/destination IPs, protocols, and data volume.
    *   It stores this flow information in a MongoDB database.
    *   This script should be run continuously in the background on a machine connected to the network you want to monitor.

2.  **Flask Web Application (`app.py`)**:
    *   A standard Flask web server that runs without special privileges.
    *   It reads the aggregated traffic data from the MongoDB database.
    *   It provides a web interface with a Sankey diagram (using ECharts) to visualize the traffic flows.
    *   The UI allows the user to designate certain IPs as "servers" to organize the visualization.

## How to Run

### 1. Setup

**a. Clone the repository and navigate into the directory.**

**b. Create a Python virtual environment:**
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows use `venv\Scripts\activate`