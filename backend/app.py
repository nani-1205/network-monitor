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
    try:
        pipeline = [
            {"$match": {"src_ip": {"$ne": "0.0.0.0"}, "dst_ip": {"$ne": "0.0.0.0"}}},
            {'$group': {'_id': '$src_ip'}},
            {'$group': {'_id': None, 'src_ips': {'$addToSet': '$_id'}}},
            {'$lookup': {
                'from': MONGO_COLLECTION_NAME,
                'pipeline': [{'$group': {'_id': '$dst_ip'}}],
                'as': 'dst_docs'
            }},
            {'$project': {
                'all_ips': {'$setUnion': ['$src_ips', '$dst_docs._id']}
            }}
        ]
        result = list(collection.aggregate(pipeline))
        if result and result[0]['all_ips']:
            ips = sorted([ip for ip in result[0]['all_ips'] if ip])
            return jsonify(ips)
        return jsonify([])
    except Exception as e:
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

        # --- Build Node List and Name Map ---
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

        # ++++++++ THE DEFINITIVE FIX: CONSOLIDATE CYCLES ++++++++
        
        # 1. Create a lookup map for fast access
        flow_map = {(f['source'], f['target']): f for f in flows}
        processed_flows = set()
        consolidated_links = []

        for flow in flows:
            source, target = flow['source'], flow['target']
            
            # Skip if we've already handled this flow as part of a pair
            if (source, target) in processed_flows:
                continue

            # Look for the reverse flow
            reverse_flow = flow_map.get((target, source))

            if reverse_flow:
                # CYCLE DETECTED: Consolidate into one link
                combined_value = flow['value'] + reverse_flow['value']
                # Clean up protocol strings
                protocol1 = flow['protocol'].strip(', ')
                protocol2 = reverse_flow['protocol'].strip(', ')
                combined_protocol = f"{protocol1} <-> {protocol2}"

                consolidated_links.append({
                    "source": node_name_map[source],
                    "target": node_name_map[target],
                    "value": combined_value,
                    "protocol": combined_protocol
                })
                # Mark both directions as processed
                processed_flows.add((source, target))
                processed_flows.add((target, source))
            else:
                # NO CYCLE: This is a one-way link
                consolidated_links.append({
                    "source": node_name_map[source],
                    "target": node_name_map[target],
                    "value": flow['value'],
                    "protocol": flow['protocol'].strip(', ')
                })
                # Mark as processed
                processed_flows.add((source, target))

        return jsonify({"nodes": nodes, "links": consolidated_links})

    except Exception as e:
        print(f"Error fetching traffic data: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)