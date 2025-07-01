import os
from flask import Flask, render_template, jsonify, request
from pymongo import MongoClient
from dotenv import load_dotenv

app = Flask(__name__)
load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME")
MONGO_COLLECTION_NAME = os.getenv("MONGO_COLLECTION_NAME")

client = MongoClient(MONGO_URI)
db = client[MONGO_DB_NAME]
collection = db[MONGO_COLLECTION_NAME]

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/hosts')
def get_hosts():
    """
    Robustly scans the database for all unique IP addresses seen,
    both as a source and a destination.
    """
    try:
        # ++++++++ THE DEFINITIVE FIX FOR HOST DISCOVERY ++++++++
        
        # 1. Create a query that finds documents where either src_ip or dst_ip is valid
        query = {
            "$and": [
                {"src_ip": {"$ne": "0.0.0.0", "$exists": True}},
                {"dst_ip": {"$ne": "0.0.0.0", "$exists": True}}
            ]
        }
        
        # 2. Use the 'distinct' method which is highly optimized for this task
        source_ips = collection.distinct("src_ip", query)
        dest_ips = collection.distinct("dst_ip", query)

        # 3. Combine the lists and get unique values
        all_ips = set(source_ips) | set(dest_ips) # The '|' operator is a set union

        # 4. Filter out any potential None values and sort
        valid_ips = sorted([ip for ip in all_ips if ip])

        return jsonify(valid_ips)
        # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++

    except Exception as e:
        print(f"Error in get_hosts: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/traffic_data')
def get_traffic_data():
    server_ips = request.args.getlist('servers[]')

    pipeline = [
        {"$match": {
            "src_ip": {"$ne": None, "$exists": True, "$ne": "0.0.0.0"},
            "dst_ip": {"$ne": None, "$exists": True, "$ne": "0.0.0.0"}
        }},
        {"$group": {
            "_id": {"source": "$src_ip", "target": "$dst_ip"},
            "value": {"$sum": "$size"},
            "protocols": {"$addToSet": "$protocol"}
        }},
        {"$project": {
            "_id": 0, "source": "$_id.source", "target": "$_id.target",
            "value": "$value", "protocol": {"$reduce": {
                "input": "$protocols", "initialValue": "",
                "in": {"$concat": ["$$value", "$$this", ", "]}
            }}
        }}
    ]

    try:
        flows = list(collection.aggregate(pipeline))
        if not flows:
            return jsonify({"nodes": [], "links": []})

        all_ips = set()
        for flow in flows:
            all_ips.add(flow['source'])
            all_ips.add(flow['target'])
            
        nodes = []
        node_name_map = {} 
        for ip in sorted(list(all_ips)):
            name = f"[S] {ip}" if ip in server_ips else f"[C] {ip}"
            nodes.append({"name": name})
            node_name_map[ip] = name

        flow_map = {(f['source'], f['target']): f for f in flows}
        processed_flows = set()
        consolidated_links = []

        for flow in flows:
            source, target = flow['source'], flow['target']
            
            if (source, target) in processed_flows:
                continue

            reverse_flow = flow_map.get((target, source))

            if reverse_flow:
                combined_value = flow['value'] + reverse_flow['value']
                protocol1 = flow['protocol'].strip(', ')
                protocol2 = reverse_flow['protocol'].strip(', ')
                combined_protocol = f"{protocol1} <-> {protocol2}" if protocol1 != protocol2 else protocol1

                consolidated_links.append({
                    "source": node_name_map[source],
                    "target": node_name_map[target],
                    "value": combined_value,
                    "protocol": combined_protocol
                })
                processed_flows.add((source, target))
                processed_flows.add((target, source))
            else:
                consolidated_links.append({
                    "source": node_name_map[source],
                    "target": node_name_map[target],
                    "value": flow['value'],
                    "protocol": flow['protocol'].strip(', ')
                })
                processed_flows.add((source, target))

        return jsonify({"nodes": nodes, "links": consolidated_links})

    except Exception as e:
        print(f"Error fetching traffic data: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)