import piece


class PieceManager(object):
    def __init__(self, torrent):
        self.torrent = torrent
        self.number_of_pieces = self.torrent.number_of_pieces
        self.total_lenght = self.torrent.total_length
        self.pieces = self.create_pieces()

    def create_pieces(self):
        pieces = []
        last_piece_num = self.number_of_pieces - 1

        for i in range(self.number_of_pieces):
            start = i * 20  # there is a 20 byte SHA1 string for each piece in .torrent file
            end = start + 20

            if i == last_piece_num:
                last_piece_length = self.torrent.total_length - (self.number_of_pieces - 1) * self.torrent.piece_length
                pieces.append(piece.Piece(i, last_piece_length, self.torrent.pieces[start:end]))
            else:
                pieces.append(piece.Piece(i, self.torrent.piece_length, self.torrent.pieces[start:end]))

        return pieces
