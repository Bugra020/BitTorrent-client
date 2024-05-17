"""
1. take torret file
2. decode torretn file
3. connect with trackers
4. make http get request
5. ???
"""
import logging
from src import torrent


class Main(object):

    def __init__(self):
        self.torrent = torrent.Torrent().load_from_path("test.torrent")



if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    main = Main()