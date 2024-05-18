import logging
import os
import random
import time
import requests
import socket
import struct
import asyncio

from bcoding import bdecode, bencode

from src import torrent


class Main(object):

    def __init__(self):
        self.start_time = None
        self.download_speed = 0
        self.downloaded_length = 0
        self.torrent = torrent.Torrent().load_from_path("../test torrents/deneme.torrent")
        self.tracker_urls = self.torrent.announce_list
        self.info_hash = self.torrent.info_hash
        self.peer_id = self.torrent.peer_id
        self.port = 6881
        self.peer_list = []

    async def start(self):
        # getting the peers
        for tracker in self.tracker_urls:
            print(f"\n{tracker[0]}")
            tracker_peer_list = self.get_peers(tracker[0][:-9])

            for tracker_peer in tracker_peer_list:
                self.peer_list.append(tracker_peer)

        print(f"all peers:{self.peer_list}")

        # Connect to peers
        connections = []
        for peer in self.peer_list:
            connections.append(await self.connect_to_peer(peer[0], peer[1]))

        # Download pieces
        print("\nSTARTING TO DOWNLOAD PIECES\n")
        piece_length = self.torrent.piece_length
        num_pieces = self.torrent.number_of_pieces
        file_path = 'test torrents\downloaded_content.dat'
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        # Create an empty file of the correct size
        with open(file_path, 'wb') as f:
            f.truncate(piece_length * num_pieces)

        self.start_time = time.time()

        for conn in connections:
            try:
                await self.download_and_save_pieces(conn[0], conn[1], file_path, num_pieces, piece_length)
                conn[1].close()
                await conn[1].wait_closed()
            except Exception as e:
                pass

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

    async def connect_to_peer(self, peer_ip, peer_port, max_retries=3, retry_delay=2, timeout=3):
        attempts = 0
        while attempts < max_retries:
            try:
                reader, writer = await asyncio.open_connection(peer_ip, peer_port)

                # Create a task to send handshake to the peer
                send_task = asyncio.create_task(self.send_handshake(reader, writer, peer_ip, peer_port))

                # Wait for the task to complete or timeout
                done, pending = await asyncio.wait([send_task], timeout=timeout, return_when=asyncio.FIRST_COMPLETED)

                # Check if the task completed successfully
                if send_task in done:
                    handshake_success = send_task.result()
                    if handshake_success:
                        print(f"Handshake with peer {peer_ip}, {peer_port} successful")
                        return reader, writer
                    else:
                        break
                else:
                    break
            except asyncio.TimeoutError:
                # Handle timeout: Retry connecting
                print(f"Connection to peer {peer_ip}, {peer_port} timed out. Retrying...")
                attempts += 1
                await asyncio.sleep(retry_delay)
            except Exception as e:
                print(f"Unexpected error occurred: {e}")
                return None

    async def send_handshake(self, reader, writer, peer_ip, peer_port):
        # constructing a handshake
        pstr = b'BitTorrent protocol'
        pstrlen = len(pstr)
        reserved = b'\x00' * 8
        handshake = bytes([pstrlen]) + pstr + reserved + self.info_hash + self.peer_id.encode()

        # sending the handshake
        writer.write(handshake)
        await writer.drain()
        print(f"\nsent a handshake to peer: {peer_ip}, {peer_port}")

        # reading the handshake response
        print(f"waiting for response: {peer_ip}, {peer_port}")
        response = await reader.read(68)

        # validating the response
        if response[28:48] != self.info_hash:
            writer.close()
            await writer.wait_closed()
            print(f"couldn't connect to peer: {peer_ip}")
            return False
        return True

    async def request_piece(self, writer, index, begin, length):
        print(f"requested the piece #{index} block #{begin / 16384}")
        request = b'\x00\x00\x00\x0d'  # Length of message
        request += b'\x06'  # Request message ID
        request += index.to_bytes(4, 'big')
        request += begin.to_bytes(4, 'big')
        request += length.to_bytes(4, 'big')
        writer.write(request)

    async def download_and_save_pieces(self, reader, writer, file_path, total_pieces, piece_length):
        for piece_index in range(total_pieces):
            piece_data = await self.download_piece(reader, writer, piece_index, piece_length)
            await self.save_piece(file_path, piece_index, piece_data, piece_length)

    async def download_piece(self, reader, writer, piece_index, piece_length):
        print(f"Started downloading piece: #{piece_index}...")
        piece = bytearray(piece_length)
        begin = 0
        block_size = 16384  # 16 KB

        while begin < piece_length:
            length = min(block_size, piece_length - begin)
            await self.request_piece(writer, piece_index, begin, length)

            response = await reader.read(4 + 1 + 8 + length)
            piece[begin:begin + length] = response[-length:]
            begin += length
            self.downloaded_length += length
            await self.display_download_speed(self.start_time, length)

        print(f"successfully downloaded the piece #{piece_index}")
        return piece

    async def display_download_speed(self, start, length):
        elapsed_time = time.time() - start
        speed = length / elapsed_time
        print(f"Current download speed: {speed:.2f} bytes/second")

    async def save_piece(self, file_path, piece_index, piece_data, piece_length):
        offset = piece_index * piece_length
        with open(file_path, 'r+b') as f:
            f.seek(offset)
            f.write(piece_data)
        print(f"successfully saved the piece #{piece_index}")


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    main = Main()
    time.sleep(1)
    asyncio.run(main.start())
