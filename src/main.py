import logging
import random
import time
import requests
import socket
import struct

from bcoding import bdecode

from src import torrent


class Main(object):

    def __init__(self):
        self.torrent = torrent.Torrent().load_from_path("../test torrents/Cities - Skylines.torrent")
        self.tracker_urls = self.torrent.announce_list
        self.info_hash = self.torrent.info_hash
        self.peer_id = self.torrent.peer_id
        self.port = 6881
        self.peer_list = []

    def start(self):
        for tracker in self.tracker_urls:
            print(f"\n{tracker[0]}")
            self.peer_list.append(self.get_peers(tracker[0][:-9]))
        print(f"all peeers:{self.peer_list}")

    def get_peers(self, announce):
        try:
            if announce.startswith('http://') or announce.startswith('https://'):
                return self.get_http_peers(announce, self.info_hash, self.peer_id, self.port)
            elif announce.startswith('udp://'):
                return self.get_udp_peers(announce, self.info_hash, self.peer_id, self.port)
            else:
                raise ValueError("Unsupported tracker protocol")
        except ConnectionResetError as e:
            # Implement retry logic or other error handling here
            print("Connection to the tracker was reset:", e)
            return []  # Return an empty list of peers if there's a connection reset error
        except socket.gaierror as e:
            print("Address-related error while resolving the host:", e)
            return []  # Return an empty list of peers if there's an address-related error

    def get_http_peers(self, announce, info_hash, peer_id, port, retries=3, timeout=5):
        try:
            for attempt in range(retries):
                try:
                    params = {
                        'info_hash': info_hash,
                        'peer_id': peer_id,
                        'port': port,
                        'uploaded': 0,
                        'downloaded': 0,
                        'left': 0,  # Total size of the files
                        'compact': 1,
                        'event': 'started'
                    }

                    response = requests.get(announce, params=params, timeout=timeout)
                    tracker_response = bdecode(response.content)

                    peers = tracker_response['peers']
                    peer_list = []

                    for i in range(0, len(peers), 6):  # tracker response contains 6 byte values for each peer
                        ip = ".".join(str(b) for b in peers[i:i + 4])
                        port = int.from_bytes(peers[i + 4:i + 6], 'big')
                        peer_list.append((ip, port))

                    print(f"got peer list successfully: {peer_list}")
                    return peer_list

                except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                    print(f"Attempt {attempt + 1} failed with error: {e}")
                    if attempt < retries - 1:
                        time.sleep(1)  # Wait a bit before retrying
                    else:
                        return []  # Return an empty list if all retries fail

        except Exception as e:
            print("Unexpected error occurred: ", e)
            return []

    def get_udp_peers(self, announce, info_hash, peer_id, client_port, retries=3, timeout=5):
        # Extract the host and port from the announce URL
        if announce.startswith('udp://'):
            announce = announce[6:]
        host, port = announce.split(':')
        print(f"host: {host}\nport: {port}")
        port = int(port)

        # Resolve the hostname to an IP address
        ip_address = socket.gethostbyname(host)

        for attempt in range(retries):
            try:
                # UDP socket
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.settimeout(timeout)

                # Connection request
                connection_id = 0x41727101980  # Initial connection ID as per the protocol
                transaction_id = random.randint(0, 0xFFFFFFFF)
                connection_request = struct.pack('>QLL', connection_id, 0, transaction_id)

                # Send connection request
                sock.sendto(connection_request, (ip_address, port))

                # Receive connection response
                response = sock.recv(16)
                if len(response) < 16:
                    raise Exception("Invalid connection response length")

                action, res_transaction_id, connection_id = struct.unpack('>LLQ', response)
                if action != 0 or res_transaction_id != transaction_id:
                    raise Exception("Invalid connection response")

                # Announce request
                downloaded = 0
                left = 0  # Change this to the actual size of the files to be downloaded
                uploaded = 0
                event = 0  # 0: none; 1: completed; 2: started; 3: stopped
                ip = 0
                key = random.randint(0, 0xFFFFFFFF)
                num_want = 50
                port = port
                announce_request = struct.pack('>QLL20s20sQQQLLLlH',
                                               connection_id, 1, transaction_id,
                                               info_hash, peer_id.encode(),
                                               downloaded, left, uploaded,
                                               event, ip, key, num_want, client_port)

                # Send announce request
                sock.sendto(announce_request, (host, port))

                # Receive announce response
                response = sock.recv(1024)
                if len(response) < 20:
                    raise Exception("Invalid announce response length")

                action, res_transaction_id, interval, leechers, seeders = struct.unpack('>LLLll', response[:20])
                if action != 1 or res_transaction_id != transaction_id:
                    raise Exception("Invalid announce response")

                peers = []
                for i in range(20, len(response), 6):
                    ip = '.'.join(str(b) for b in response[i:i + 4])
                    port = int.from_bytes(response[i + 4:i + 6], 'big')
                    peers.append((ip, port))

                print(f"peers: {peers}\ngot peers successfully from: {host}")
                return peers

            except (socket.timeout, ConnectionResetError) as e:
                print(f"Attempt {attempt + 1} failed with error: {e}")
                if attempt < retries - 1:
                    time.sleep(1)  # Wait a bit before retrying
                else:
                    return []  # Return an empty list if all retries fail
            except Exception as e:
                print("Unexpected error occurred: ", e)
                return []


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    main = Main()
    time.sleep(3)
    main.start()
