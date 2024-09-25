# Copyright 2024 Clerk Ma
import os, sys, argparse
import struct
from collections import namedtuple
from PySide6.QtGui import (
    QFont, QIcon
)
from PySide6.QtWidgets import (
    QApplication, QPushButton, QLabel, QWidget,
    QVBoxLayout, QHBoxLayout, QGroupBox, QScrollArea,
    QDialog, QTableWidget, QTableWidgetItem
)

SFNT_MAGIC_1 = [0x4F54544F, 0x00010000]
SFNT_MAGIC_N = [0x74746366]

name_entry = namedtuple("name_entry", [
    "platform_id", "encoding_id", "language_id",
    "name_id", "string"
])

class FileParser:
    font_list = []
    def __init__(self, filename):
        with open(filename, "rb") as src:
            self.data = src.read()
            try:
                offset_list = self.parse_offset_list()
                for x in offset_list:
                    font = self.parse_one(x)
                    self.font_list.append(font)
            except Exception as error:
                print("Error", error)

    def parse_offset_list(self):
        magic = struct.unpack_from(">L", self.data)[0]
        if magic in SFNT_MAGIC_N:
            _, _, _, count = struct.unpack_from(">LHHL", self.data, 0)
            return struct.unpack_from(f">{count}L", self.data, 12)
        elif magic in SFNT_MAGIC_1:
            return [0]
        return []

    def parse_one(self, offset):
        _, count, _, _, _ = struct.unpack_from(">L4H", self.data, offset)
        table_list = []
        for x in range(count):
            table = struct.unpack_from(">4s3L", self.data, offset + 12 + 16 * x)
            table_list.append(table)
        return table_list

    def seg(self, data, start, length):
        return data[start:start+length]

    def parse_name(self, table):
        data = self.seg(self.data, table[2], table[3])
        _, count, offset = struct.unpack_from(">3H", data, 0)
        name_list = []
        for i in range(count):
            entry = struct.unpack_from(">6H", data, 6 + 12 * i)
            if entry[0] == 3:
                string_b = self.seg(data, offset + entry[5], entry[4])
                if entry[1] == 4:
                    string_u = string_b.decode("cp936")
                elif entry[1] == 5:
                    string_u = string_b.decode("cp950")
                elif entry[1] == 6:
                    string_u = string_b.decode("cp949")
                elif entry[1] == 7:
                    string_u = string_b.decode("johab")
                else:
                    string_u = string_b.decode("utf_16_be")
                name_list.append(name_entry._make([*entry[:4], string_u]))
        return name_list

class DirectoryWidget(QScrollArea):
    def __init__(self, filename, *args, **kwargs):
        super(DirectoryWidget, self).__init__(*args, **kwargs)
        self.p = FileParser(filename)
        l = len(self.p.font_list)
        layout = QVBoxLayout()
        if l >= 1:
            layout.addWidget(QLabel(f"File path: '{filename}'"))
        if l > 1:
            for x_idx, x in enumerate(self.p.font_list):
                g = QGroupBox(f"Index={x_idx}")
                g_layout = QVBoxLayout()
                for y in x:
                    self.format_table(y, g_layout)
                g.setLayout(g_layout)
                layout.addWidget(g)
        elif l == 1:
            for y in self.p.font_list[0]:
                self.format_table(y, layout)
        else:
            label = QLabel(f"Failed to parse file '{filename}'")
            layout.addWidget(label)
        widget = QWidget()
        self.setWidgetResizable(True)
        self.setWidget(widget)
        widget.setLayout(layout)

    def format_table(self, one, layout):
        t = one[0].decode("u8")
        c = "0x%08X" % one[1]
        o = "%10d" % one[2]
        l = "%10d" % one[3]
        label = QLabel(f"{t}, {c}, {o}, {l}")
        if t == 'name':
            h = QHBoxLayout()
            h.addWidget(label)
            b = QPushButton("show")
            h.addWidget(b)
            b.clicked.connect(lambda checked=False, table=one: self.show_name(table))
            layout.addLayout(h)
        else:
            layout.addWidget(label)

    def show_name(self, table):
        data = self.p.parse_name(table)
        dialog = QDialog()
        dialog.setWindowTitle("'name' table")
        dialog.setFixedSize(600, 400)
        table = QTableWidget()
        table.setRowCount(len(data))
        table.setColumnCount(5)
        for cid, col in enumerate(["platform ID", "encoding ID", "language ID", "name ID", "string"]):
            table.setHorizontalHeaderItem(cid, QTableWidgetItem(col))
        for rid, row in enumerate(data):
            for cid, col in enumerate(row):
                table.setItem(rid, cid, QTableWidgetItem(f"{col}"))
        layout = QVBoxLayout()
        layout.addWidget(table)
        dialog.setLayout(layout)
        dialog.exec()

def get_platform_style():
    p = sys.platform
    n = "Courier"
    if p == "nt":
        n = "Consolas"
    elif p == "darwin":
        n = "Menlo"
    return f"font-family: '{n}';"

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog='sfnt-p',
        description='SFNT Proofer'
    )
    parser.add_argument('filename')
    args = parser.parse_args()
    if (filename := args.filename) and os.path.isfile(filename):
        app = QApplication()
        app.setWindowIcon(QIcon.fromTheme(QIcon.ThemeIcon.Scanner))
        widget = DirectoryWidget(filename)
        widget.setWindowTitle("SFNT Proofer")
        widget.setFixedSize(450, 400)
        widget.setStyleSheet(get_platform_style())
        widget.show()
        sys.exit(app.exec())
