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
            {'$match': {"src_ip": {"$ne": "0.0.0.0"}, "dst_ip": {"$ne": "0.0.0.0"}}},
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
            "_id": {"source": "$src_ip", "target": "$dst_ip", "protocol": "$protocol"},
            "value": {"$sum": "$size"}
        }},
        {"$project": {
            "_id": 0, "source": "$_id.source", "target": "$_id.target",
            "protocol": "$_id.protocol", "value": "$value"
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

        links = []
        for flow in flows:
            source_ip = flow.get('source')
            target_ip = flow.get('target')
            
            if source_ip in node_name_map and target_ip in node_name_map:
                links.append({
                    "source": node_name_map[source_ip],
                    "target": node_name_map[target_ip],
                    "value": flow['value'],
                    "protocol": flow['protocol']
                })
        
        return jsonify({"nodes": nodes, "links": links})

    except Exception as e:
        print(f"Error fetching traffic data: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)