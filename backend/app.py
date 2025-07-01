import os
from flask import Flask, render_template, jsonify, request
from pymongo import MongoClient
from dotenv import load_dotenv
from collections import defaultdict

# --- Flask & DB Setup ---
app = Flask(__name__)
load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME")
MONGO_COLLECTION_NAME = os.getenv("MONGO_COLLECTION_NAME")

client = MongoClient(MONGO_URI)
db = client[MONGO_DB_NAME]
collection = db[MONGO_COLLECTION_NAME]

# --- Routes ---
@app.route('/')
def index():
    """Render the main dashboard page."""
    return render_template('index.html')

@app.route('/api/hosts')
def get_hosts():
    """
    Scans the database for all unique IP addresses seen.
    This acts as our network discovery.
    """
    try:
        # Use an aggregation pipeline to find unique IPs efficiently
        pipeline = [
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
            # Filter out None or empty values and sort
            ips = sorted([ip for ip in result[0]['all_ips'] if ip])
            return jsonify(ips)
        return jsonify([])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/traffic_data')
def get_traffic_data():
    """
    Aggregates traffic data from MongoDB to be used in the Sankey diagram.
    """
    # The UI will send a list of IPs marked as 'servers'
    server_ips = request.args.getlist('servers[]')

    pipeline = [
        {
            "$group": {
                "_id": {
                    "source": "$src_ip",
                    "target": "$dst_ip",
                    "protocol": "$protocol"
                },
                "value": {"$sum": "$size"} # Aggregate by total bytes
            }
        },
        {
            "$project": {
                "_id": 0,
                "source": "$_id.source",
                "target": "$_id.target",
                "protocol": "$_id.protocol",
                "value": "$value"
            }
        }
    ]

    try:
        flows = list(collection.aggregate(pipeline))
        if not flows:
            return jsonify({"nodes": [], "links": []})

        # --- Process data for Sankey format ---
        all_ips = set()
        for flow in flows:
            all_ips.add(flow['source'])
            all_ips.add(flow['target'])

        # Nodes are all the unique IPs
        nodes = [{"name": ip} for ip in sorted(list(all_ips))]
        
        # Add labels to distinguish clients from servers in the visualization
        for node in nodes:
            if node["name"] in server_ips:
                node["name"] = f"[S] {node['name']}" # [S] for Server
            else:
                node["name"] = f"[C] {node['name']}" # [C] for Client

        # Links are the flows between nodes
        links = []
        for flow in flows:
            # We need to match the source/target with the modified node names
            source_name = f"[S] {flow['source']}" if flow['source'] in server_ips else f"[C] {flow['source']}"
            target_name = f"[S] {flow['target']}" if flow['target'] in server_ips else f"[C] {flow['target']}"

            links.append({
                "source": source_name,
                "target": target_name,
                "value": flow['value'],
                "protocol": flow['protocol']
            })

        return jsonify({"nodes": nodes, "links": links})

    except Exception as e:
        print(f"Error fetching traffic data: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)