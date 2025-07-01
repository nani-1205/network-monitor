import os
from flask import Flask, render_template, jsonify, request
from pymongo import MongoClient
from dotenv import load_dotenv
import ipaddress # New import for checking private/public IPs

app = Flask(__name__)
load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME")
MONGO_COLLECTION_NAME = os.getenv("MONGO_COLLECTION_NAME")

client = MongoClient(MONGO_URI)
db = client[MONGO_DB_NAME]
collection = db[MONGO_COLLECTION_NAME]

# --- Helper Function ---
def is_private_ip(ip_str):
    """Checks if an IP address is in a private range."""
    try:
        ip = ipaddress.ip_address(ip_str)
        return ip.is_private or ip.is_multicast or ip.is_link_local
    except ValueError:
        return False

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/hosts')
def get_hosts():
    try:
        query = {"$and": [{"src_ip": {"$ne": "0.0.0.0", "$exists": True}}, {"dst_ip": {"$ne": "0.0.0.0", "$exists": True}}]}
        source_ips, dest_ips = collection.distinct("src_ip", query), collection.distinct("dst_ip", query)
        all_ips = set(source_ips) | set(dest_ips)
        # Sort IPs with private ones first
        valid_ips = sorted([ip for ip in all_ips if ip], key=lambda ip: (not is_private_ip(ip), ip))
        return jsonify(valid_ips)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/traffic_data')
def get_traffic_data():
    focus_ip = request.args.get('focus_ip', None)
    
    pipeline = [{"$match": {"src_ip": {"$ne": None, "$exists": True, "$ne": "0.0.0.0"}, "dst_ip": {"$ne": None, "$exists": True, "$ne": "0.0.0.0"}}}]
    if focus_ip:
        pipeline.append({"$match": {"$or": [{"src_ip": focus_ip}, {"dst_ip": focus_ip}]}})

    pipeline.extend([
        {"$group": {"_id": {"source": "$src_ip", "target": "$dst_ip"}, "value": {"$sum": "$size"}, "ports": {"$addToSet": "$dst_port"}}},
        {"$project": {"_id": 0, "source": "$_id.source", "target": "$_id.target", "value": "$value", "ports": "$ports"}}
    ])

    try:
        flows = list(collection.aggregate(pipeline))
        if not flows: return jsonify({"nodes": [], "links": []})

        nodes, links = [], []
        all_ips = set()
        for flow in flows:
            all_ips.add(flow['source'])
            all_ips.add(flow['target'])
        
        # ++++++++ NEW LAYOUT LOGIC ++++++++
        node_depth_map = {}
        for ip in sorted(list(all_ips)):
            # Assign depth: 0 for internal, 1 for external
            depth = 0 if is_private_ip(ip) else 1
            nodes.append({"name": ip, "depth": depth})
            node_depth_map[ip] = depth
        
        for flow in flows:
            source_ip, target_ip = flow['source'], flow['target']
            
            # Ensure the flow is between different columns (Internal -> External)
            # Or between two internal hosts (Internal -> Internal)
            source_depth = node_depth_map.get(source_ip)
            target_depth = node_depth_map.get(target_ip)
            
            if source_depth is None or target_depth is None: continue

            # If an external server talks to another external server, skip for clarity
            if source_depth == 1 and target_depth == 1: continue

            links.append({
                "source": source_ip,
                "target": target_ip,
                "value": flow.get('value', 1),
                "ports": sorted(list(filter(None, flow.get('ports', []))))
            })
            
        return jsonify({"nodes": nodes, "links": links})

    except Exception as e:
        print(f"Error fetching traffic data: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)