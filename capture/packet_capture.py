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
    It now logs ALL IP traffic it sees, which is necessary for a complete graph.
    """
    if IP in packet:
        src_ip = packet[IP].src
        dst_ip = packet[IP].dst
        protocol = get_protocol_name(packet)
        size = len(packet)
        timestamp = datetime.utcnow()

        # The restrictive "is_local_traffic" filter has been REMOVED.
        # This ensures all flows are captured, allowing the Sankey diagram
        # to be built correctly.

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
    # Check for root privileges (required for packet sniffing)
    # Note: On Windows, you just need to run the terminal as Administrator.
    # The os.geteuid() check is for Unix-like systems.
    try:
        if os.geteuid() != 0:
            print("❌ This script requires root/administrator privileges to capture packets.")
            print("Please run with 'sudo python packet_capture.py' or as an Administrator.")
            sys.exit(1)
    except AttributeError:
        # This will be raised on Windows, where os.geteuid() doesn't exist.
        # We can't programmatically check for Admin rights easily, so we'll just proceed
        # and let the user know if scapy fails.
        print("ℹ️ Running on Windows. Please ensure you are running this script in a terminal with Administrator privileges.")


    print("🚀 Starting network packet capture...")
    print(f"Listening on interface: {INTERFACE or 'default'}")
    print("Data will be stored in MongoDB. Press Ctrl+C to stop.")

    try:
        # L2-socket is often needed for more reliable capture
        sniff(iface=INTERFACE, prn=packet_callback, store=0)
    except Exception as e:
        print(f"\nAn error occurred during sniffing: {e}")
        print("Ensure the specified interface exists and you have permissions (run with sudo/Admin).")

if __name__ == "__main__":
    main()