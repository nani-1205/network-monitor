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
INTERFACE = os.getenv("CAPTURE_INTERFACE") or None # Let scapy choose if not set

# --- Database Connection ---
try:
    client = MongoClient(MONGO_URI)
    db = client[MONGO_DB_NAME]
    collection = db[MONGO_COLLECTION_NAME]
    # Create an index to speed up queries
    collection.create_index([("timestamp", -1)])
    print("✅ Successfully connected to MongoDB.")
except Exception as e:
    print(f"❌ Could not connect to MongoDB: {e}")
    sys.exit(1)

def get_protocol_name(packet):
    """A simplified protocol identifier."""
    if packet.haslayer(TCP):
        if packet[TCP].dport == 80 or packet[TCP].sport == 80:
            return "HTTP"
        if packet[TCP].dport == 443 or packet[TCP].sport == 443:
            return "HTTPS"
        if packet[TCP].dport == 22 or packet[TCP].sport == 22:
            return "SSH"
        if packet[TCP].dport == 9418 or packet[TCP].sport == 9418:
            return "GIT"
        if packet[TCP].dport == 445 or packet[TCP].sport == 445:
            return "SMB"
        return "TCP"
    if packet.haslayer(UDP):
        if packet[UDP].dport == 53 or packet[UDP].sport == 53:
            return "DNS"
        return "UDP"
    return "Other"


def packet_callback(packet):
    """
    This function is called for every packet sniffed.
    """
    if IP in packet:
        src_ip = packet[IP].src
        dst_ip = packet[IP].dst
        protocol = get_protocol_name(packet)
        size = len(packet)
        timestamp = datetime.utcnow()

        # We only care about local traffic for this example
        # This is a simple filter, you might want to adjust it
        is_local_traffic = src_ip.startswith("192.168.") or \
                           dst_ip.startswith("192.168.") or \
                           src_ip.startswith("10.") or \
                           dst_ip.startswith("10.")

        if not is_local_traffic:
            return # Skip non-local traffic

        flow_data = {
            "timestamp": timestamp,
            "src_ip": src_ip,
            "dst_ip": dst_ip,
            "protocol": protocol,
            "size": size,
        }

        try:
            collection.insert_one(flow_data)
            print(f"Logged: {timestamp} | {src_ip} -> {dst_ip} ({protocol}) [{size} bytes]")
        except Exception as e:
            print(f"Error inserting into DB: {e}")


def main():
    """Main function to start sniffing."""
    # Check for root privileges
    if os.geteuid() != 0:
        print("❌ This script requires root privileges to capture packets.")
        print("Please run with 'sudo python packet_capture.py'")
        sys.exit(1)

    print("🚀 Starting network packet capture...")
    print(f"Listening on interface: {INTERFACE or 'default'}")
    print("Data will be stored in MongoDB. Press Ctrl+C to stop.")

    try:
        # L2-socket is often needed for more reliable capture
        sniff(iface=INTERFACE, prn=packet_callback, store=0)
    except Exception as e:
        print(f"An error occurred during sniffing: {e}")
        print("Ensure the specified interface exists and you have permissions.")

if __name__ == "__main__":
    main()