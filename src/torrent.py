import logging
import math, hashlib, os, string, random
from bcoding import bencode, bdecode


class Torrent(object):
    def __init__(self):
        self.torrent_file = {}
        self.total_length: int = 0
        self.piece_length: int = 0
        self.pieces: int = 0
        self.info_hash: str = ''
        self.peer_id: str = ''
        self.announce_list = ''
        self.file_names = []
        self.number_of_pieces: int = 0

    def load_from_path(self, path):
        with open(path, 'rb') as file:
            contents = bdecode(file)

        self.torrent_file = contents
        self.piece_length = self.torrent_file['info']['piece length']
        self.pieces = self.torrent_file['info']['pieces']
        self.info_hash = hashlib.sha1(bencode(self.torrent_file['info'])).digest()
        self.peer_id = self.generate_peer_id()
        self.announce_list = self.get_trackers()
        self.init_files()
        self.number_of_pieces = math.ceil(self.total_length / self.piece_length)

        logging.debug(self.announce_list)
        logging.debug(self.file_names)

        assert (self.total_length > 0)
        assert (len(self.file_names) > 0)

        #print(f"{self.total_length} {self.number_of_pieces} {self.announce_list} {self.file_names} {self.peer_id}")

        return self

    def init_files(self):
        root = self.torrent_file['info']['name']

        if 'files' in self.torrent_file['info']:
            if not os.path.exists(root):
                os.mkdir(root, 0o0766)

            for file in self.torrent_file['info']['files']:
                file_path = os.path.join(root, *file["path"])

                if not os.path.exists(os.path.dirname(file_path)):
                    os.makedirs(os.path.dirname(file_path))

                self.file_names.append({"path": file_path, "length": file["length"]})
                self.total_length += file["length"]

        else:
            self.file_names.append({"path": root, "length": self.torrent_file['info']['length']})
            self.total_length = self.torrent_file['info']['length']

    def get_trackers(self):
        if 'announce-list' in self.torrent_file:
            return self.torrent_file['announce-list']
        else:
            return [[self.torrent_file['announce']]]

    def generate_peer_id(self):
        id = "-BK0001-"
        for i in range(0, 12, 1):
            id += random.choice(string.digits)
        return id
        # seed = str(time.time())
        # return hashlib.sha1(seed.encode('utf-8')).digest()
