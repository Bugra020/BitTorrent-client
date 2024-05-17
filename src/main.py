"""
1. take torret file *
2. decode torretn file *
3. connect with trackers
4. make http get request
5. ???
"""
import logging, requests
from src import torrent
from bcoding import bencode, bdecode


class Main(object):

    def __init__(self):
        self.torrent = torrent.Torrent().load_from_path("test.torrent")
        self.tracker_urls = self.torrent.announce_list

    def get_peers(self, announce, info_hash, peer_id, port):
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

        response = requests.get(announce, params=params)
        tracker_response = bdecode(response.content)

        peers = tracker_response[b'peers']
        peer_list = []

        for i in range(0, len(peers), 6):  # tracker response contains 6 byte values for each peer
            ip = ".".join(str(b) for b in peers[i:i + 4])
            port = int.from_bytes(peers[i + 4:i + 6], 'big')
            peer_list.append((ip, port))

        return peer_list


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    main = Main()
