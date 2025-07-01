import os
import sys
from datetime import datetime
from scapy.all import sniff, IP, TCP, UDP
from pymongo import MongoClient
from dotenv import load_dotenv

# --- Configuration ---
load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME")
MONGO_COLLECTION_NAME = os.getenv("MONGO_COLLECTION_NAME")
INTERFACE = os.getenv("CAPTURE_INTERFACE") or None

# --- Database Connection ---
try:
    client = MongoClient(MONGO_URI)
    db = client[MONGO_DB_NAME]
    collection = db[MONGO_COLLECTION_NAME]
    collection.create_index([("timestamp", -1)])
    print("✅ Successfully connected to MongoDB.")
except Exception as e:
    print(f"❌ Could not connect to MongoDB: {e}")
    sys.exit(1)

def get_protocol_name(packet):
    """A simplified protocol identifier."""
    if packet.haslayer(TCP):
        if packet[TCP].dport == 80 or packet[TCP].sport == 80: return "HTTP"
        if packet[TCP].dport == 443 or packet[TCP].sport == 443: return "HTTPS"
        if packet[TCP].dport == 22 or packet[TCP].sport == 22: return "SSH"
        if packet[TCP].dport == 9418 or packet[TCP].sport == 9418: return "GIT"
        if packet[TCP].dport == 445 or packet[TCP].sport == 445: return "SMB"
        return "TCP"
    if packet.haslayer(UDP):
        if packet[UDP].dport == 53 or packet[UDP].sport == 53: return "DNS"
        return "UDP"
    return "Other"

def packet_callback(packet):
    """
    This function is called for every packet sniffed.
    It now logs the destination port for TCP/UDP traffic.
    """
    if IP in packet:
        src_ip = packet[IP].src
        dst_ip = packet[IP].dst
        protocol = get_protocol_name(packet)
        size = len(packet)
        timestamp = datetime.utcnow()

        flow_data = {
            "timestamp": timestamp,
            "src_ip": src_ip,
            "dst_ip": dst_ip,
            "protocol": protocol,
            "size": size,
            "dst_port": None # Default to None
        }

        # Add destination port for TCP and UDP packets
        if TCP in packet:
            flow_data["dst_port"] = packet[TCP].dport
        elif UDP in packet:
            flow_data["dst_port"] = packet[UDP].dport

        try:
            collection.insert_one(flow_data)
            # Add port to the log message for real-time feedback
            port_str = f":{flow_data['dst_port']}" if flow_data['dst_port'] else ""
            print(f"Logged: {timestamp} | {src_ip} -> {dst_ip}{port_str} ({protocol}) [{size} bytes]")
        except Exception as e:
            print(f"Error inserting into DB: {e}")

def main():
    """Main function to start sniffing."""
    try:
        if os.geteuid() != 0:
            print("❌ This script requires root/administrator privileges to capture packets.")
            print("Please run with 'sudo python packet_capture.py' or as an Administrator.")
            sys.exit(1)
    except AttributeError:
        print("ℹ️ Running on Windows. Please ensure you are running this script in a terminal with Administrator privileges.")

    print("🚀 Starting network packet capture...")
    print(f"Listening on interface: {INTERFACE or 'default'}")
    print("Data will be stored in MongoDB. Press Ctrl+C to stop.")

    try:
        sniff(iface=INTERFACE, prn=packet_callback, store=0)
    except Exception as e:
        print(f"\nAn error occurred during sniffing: {e}")
        print("Ensure the specified interface exists and you have permissions (run with sudo/Admin).")

if __name__ == "__main__":
    main()