# Copyright 2024 Clerk Ma
import os, sys, argparse
import struct
from PySide6.QtWidgets import QApplication, QPushButton, QLabel, QWidget, QVBoxLayout, QGroupBox, QScrollArea

SFNT_MAGIC_1 = [0x4F54544F, 0x00010000]
SFNT_MAGIC_N = [0x74746366]

class FileParser:
    font_list = []
    def __init__(self, filename):
        with open(filename, "rb") as src:
            data = src.read()
            try:
                offset_list = self.parse_offset_list(data)
                for x in offset_list:
                    font = self.parse_one(data, x)
                    self.font_list.append(font)
            except Exception as error:
                print("Error", error)

    def parse_offset_list(self, data):
        magic = struct.unpack_from(">L", data)[0]
        if magic in SFNT_MAGIC_N:
            _, _, _, count = struct.unpack_from(">LHHL", data, 0)
            return struct.unpack_from(f">{count}L", data, 12)
        elif magic in SFNT_MAGIC_1:
            return [0]
        return []

    def parse_one(self, data, offset):
        _, count, _, _, _ = struct.unpack_from(">L4H", data, offset)
        table_list = []
        for x in range(count):
            table = struct.unpack_from(">4s3L", data, offset + 12 + 16 * x)
            table_list.append(table)
        return table_list

class DirectoryWidget(QScrollArea):
    def __init__(self, filename, *args, **kwargs):
        super(DirectoryWidget, self).__init__(*args, **kwargs)
        p = FileParser(filename)
        l = len(p.font_list)
        layout = QVBoxLayout()
        if l >= 1:
            layout.addWidget(QLabel(f"File path: '{filename}'"))
        if l > 1:
            for x_idx, x in enumerate(p.font_list):
                g = QGroupBox(f"Index={x_idx}")
                g_layout = QVBoxLayout()
                for y in x:
                    label = self.format_table(y)
                    g_layout.addWidget(label)
                g.setLayout(g_layout)
                layout.addWidget(g)
        elif l == 1:
            for y in p.font_list[0]:
                label = self.format_table(y)
                layout.addWidget(label)
        else:
            label = QLabel(f"Failed to parse file '{filename}'")
            layout.addWidget(label)
        widget = QWidget()
        self.setWidgetResizable(True)
        self.setWidget(widget)
        widget.setLayout(layout)
    
    def format_table(self, one):
        t = one[0].decode("u8")
        c = "0x%08X" % one[1]
        o = "%10d" % one[2]
        l = "%10d" % one[3]
        return QLabel(f"{t}, {c}, {o}, {l}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog='sfnt-p',
        description='SFNT Proofer'
    )
    parser.add_argument('filename')
    args = parser.parse_args()
    if (filename := args.filename) and os.path.isfile(filename):
        print(filename)
        app = QApplication()
        widget = DirectoryWidget(filename)
        widget.setWindowTitle("SFNT Proofer")
        widget.setFixedSize(400, 400)
        widget.setStyleSheet("font-family: 'Consolas', 'Microsoft Yahei';")
        widget.show()
        sys.exit(app.exec())
