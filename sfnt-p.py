# Copyright 2024 Clerk Ma
import os, sys, argparse
import struct
from collections import namedtuple
from PySide6.QtGui import (
    QFont, QIcon, Qt
)
from PySide6.QtWidgets import (
    QApplication, QPushButton, QLabel, QWidget,
    QVBoxLayout, QHBoxLayout, QGroupBox, QScrollArea,
    QDialog, QTableWidget, QTableWidgetItem, QSizePolicy, QLayout
)

SFNT_MAGIC_1 = [0x4F54544F, 0x00010000]
SFNT_MAGIC_N = [0x74746366]

head_table = namedtuple("head_table", [
    "major_version", "minor_version", "font_revision",
    "checksum_adjustment", "magic_number",
    "flags", "units_per_em", "created", "modified",
    "x_min", "y_min", "x_max", "y_max", "mac_style",
    "lowest_rec_ppem", "font_direction_hint", "index_to_loc_format",
    "glyph_data_format"
])
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

    def parse_head(self, table):
        data = self.seg(self.data, table[2], table[3])
        vars = struct.unpack_from(">2H3L2H2Q4h2H3h", data, 0)
        return head_table._make(vars)

    def parse_gsub_gpos(self, table):
        data = self.seg(self.data, table[2], table[3])
        _, _, s_list_offset, f_list_offset, _ = struct.unpack_from(">5H", data, 0)
        s_list = []
        s_list_count = struct.unpack_from(">H", data, s_list_offset)[0]
        for x in range(s_list_count):
            script_tag, s_offset = struct.unpack_from(">4sH", data, s_list_offset + 2 + 6 * x)
            s_offset += s_list_offset
            default_lang_sys_offset, l_count = struct.unpack_from(">2H", data, s_offset)
            lang_sys = []
            for y in range(l_count):
                lang_tag, lang_sys_offset = struct.unpack_from(">4sH", data, s_offset + 4 + 6 * y)
                lang_sys_offset += s_offset
                _, required, f_count = struct.unpack_from(">3H", data, lang_sys_offset)
                feature = struct.unpack_from(f">{f_count}H", data, lang_sys_offset + 6)
                lang_sys.append((lang_tag.decode("u8"), required, feature))
            s_list.append((script_tag.decode("u8"), lang_sys))
        return s_list

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
        if t in ["head", "name", "GPOS", "GSUB"]:
            h = QHBoxLayout()
            h.addWidget(label)
            b = QPushButton("show")
            h.addWidget(b)
            if t == "name":
                b.clicked.connect(lambda checked=False, table=one: self.show_name(table))
            elif t == "head":
                b.clicked.connect(lambda checked=False, table=one: self.show_head(table))
            elif t in ["GPOS", "GSUB"]:
                b.clicked.connect(lambda checked=False, table=one: self.show_gsub_gpos(table))
            layout.addLayout(h)
        else:
            layout.addWidget(label)

    def show_name(self, table):
        data = self.p.parse_name(table)
        dialog = QDialog()
        dialog.setWindowTitle("'name' table")
        dialog.setFixedSize(600, 400)
        table = QTableWidget(dialog)
        table.setFixedSize(600, 400)
        table.setRowCount(len(data))
        table.setColumnCount(5)
        for cid, col in enumerate(["platform ID", "encoding ID", "language ID", "name ID", "string"]):
            table.setHorizontalHeaderItem(cid, QTableWidgetItem(col))
        for rid, row in enumerate(data):
            for cid, col in enumerate(row):
                item = QTableWidgetItem(f"{col}")
                table.setItem(rid, cid, item)
                if cid == 4:
                    item.setToolTip(f"{col}")
        dialog.exec()

    def show_head(self, table):
        data = self.p.parse_head(table)
        dialog = QDialog()
        dialog.setWindowTitle("'head' table")
        dialog.setFixedSize(600, 400)
        table = QTableWidget(dialog)
        table.setFixedSize(600, 400)
        table.setRowCount(len(data))
        table.setColumnCount(1)
        for kid, key in enumerate(head_table._fields):
            table.setVerticalHeaderItem(kid, QTableWidgetItem(key))
        for vid, val in enumerate(data):
            table.setItem(vid, 0, QTableWidgetItem(f"{val}"))
        dialog.exec()

    def show_gsub_gpos(self, table):
        data = self.p.parse_gsub_gpos(table)
        dialog = QDialog()
        dialog.setWindowTitle(f"'{table[0].decode('u8')}' table")
        dialog.setFixedSize(600, 400)
        scroll = QScrollArea(dialog)
        scroll.setFixedSize(600, 400)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        scroll.setWidgetResizable(True)
        layout = QVBoxLayout(scroll)
        for s in data:
            s_tag = s[0]
            group = QGroupBox(s_tag)
            layout.addWidget(group)
            if s[1]:
                lang_layout = QVBoxLayout(group)
                for l in s[1]:
                    lang_layout.addWidget(QLabel(l[0]))
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
