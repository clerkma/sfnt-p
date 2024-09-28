# Copyright 2024 Clerk Ma
import os, sys, argparse
import struct
from collections import namedtuple
from PySide6.QtCore import (
    QSize
)
from PySide6.QtGui import (
    QFont, QIcon, Qt, QColor
)
from PySide6.QtWidgets import (
    QApplication, QPushButton, QLabel, QWidget,
    QVBoxLayout, QHBoxLayout, QGroupBox, QScrollArea,
    QDialog, QTableWidget, QTableWidgetItem, QListWidget, QListWidgetItem,
    QListView, QMessageBox
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
xhea_table = namedtuple("xhea_table", [
    "ascender", "descender", "line_gap", "advance_width_max",
    "min_left_side_bearing", "min_right_side_bearing", "x_max_extent",
    "caret_slope_rise", "caret_slope_run", "caret_offset",
    "metric_data_format", "number_of_h_metrics"
])
xhea_translation = {
    "_width_": "_height_",
    "_left_": "_top_",
    "_right_": "_bottom_",
    "_h_": "_v_",
    "x_max_": "y_max_",
}

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

    def parse_xhea(self, table):
        data = self.seg(self.data, table[2], table[3])
        vars = struct.unpack_from(">2H3hH3h3h8xhH", data, 0)
        return xhea_table._make(vars[2:])

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
            if default_lang_sys_offset:
                default_lang_sys_offset += s_offset
                _, required, f_count = struct.unpack_from(">3H", data, default_lang_sys_offset)
                feature = struct.unpack_from(f">{f_count}H", data, default_lang_sys_offset + 6)
                default_lang_sys = feature
            else:
                default_lang_sys = None
            lang_sys = []
            for y in range(l_count):
                lang_tag, lang_sys_offset = struct.unpack_from(">4sH", data, s_offset + 4 + 6 * y)
                lang_sys_offset += s_offset
                _, required, f_count = struct.unpack_from(">3H", data, lang_sys_offset)
                feature = struct.unpack_from(f">{f_count}H", data, lang_sys_offset + 6)
                lang_sys.append((lang_tag.decode("u8"), required, feature))
            s_list.append((script_tag.decode("u8"), default_lang_sys, lang_sys))
        f_list = []
        f_list_count = struct.unpack_from(">H", data, f_list_offset)[0]
        for x in range(f_list_count):
            feature_tag, _ = struct.unpack_from(">4sH", data, f_list_offset + 2 + 6 * x)
            f_list.append(feature_tag.decode("u8"))
        return s_list, f_list

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
        h = QHBoxLayout()
        h.addWidget(label)
        b = QPushButton("show")
        h.addWidget(b)
        if t == "name":
            b.clicked.connect(lambda checked, table=one: self.show_name(table))
        elif t == "head":
            b.clicked.connect(lambda checked, table=one: self.show_head(table))
        elif t in ["GPOS", "GSUB"]:
            b.clicked.connect(lambda checked, table=one: self.show_gsub_gpos(table))
        elif t in ["hhea", "vhea"]:
            b.clicked.connect(lambda checked, table=one: self.show_xhea(table))
        else:
            b.clicked.connect(lambda checked, table=one: self.show_not_implemented_message(table))
        layout.addLayout(h)

    def show_not_implemented_message(self, table):
        message_box = QMessageBox()
        message_box.information(
            self, f"'{table[0].decode('u8')}' table",
            "not implemented ..."
        )

    def show_name(self, table):
        data = self.p.parse_name(table)
        dialog = QDialog()
        dialog.setWindowTitle("'name' table")
        dialog.setFixedSize(600, 400)
        table = QTableWidget(dialog)
        table.setFixedSize(600, 400)
        table.setRowCount(len(data))
        table.setColumnCount(5)
        for cid, col in enumerate(name_entry._fields):
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

    def show_xhea(self, table):
        data = self.p.parse_xhea(table)
        dialog = QDialog()
        tag = table[0].decode('u8')
        dialog.setWindowTitle(f"'{tag}' table")
        dialog.setFixedSize(600, 400)
        table = QTableWidget(dialog)
        table.setFixedSize(600, 400)
        table.setRowCount(len(data))
        table.setColumnCount(1)
        for kid, key in enumerate(xhea_table._fields):
            real_key = key
            if tag == "vhea":
                real_key = key
                for src, dst in xhea_translation.items():
                    real_key = real_key.replace(src, dst)
            table.setVerticalHeaderItem(kid, QTableWidgetItem(real_key))
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
        widget = QWidget()
        layout = QVBoxLayout(widget)
        f_count = len(data[1])
        for s in data[0]:
            s_tag, s_dflt, s_list = s
            group = QGroupBox(s_tag)
            layout.addWidget(group)
            lang_layout = QVBoxLayout(group)
            if s_dflt:
                lang_layout.addWidget(QLabel("DFLT"))
                tag_widget = QListWidget()
                tag_widget.setFlow(QListView.LeftToRight)
                for l in s_dflt:
                    if l < f_count:
                        tag_widget.addItem("%s" % data[1][l])
                lang_layout.addWidget(tag_widget)
            if s_list:
                for l_tag, l_req, l_list in s_list:
                    print(l_req)
                    lang_layout.addWidget(QLabel(l_tag))
                    tag_widget = QListWidget()
                    tag_widget.setFlow(QListView.LeftToRight)
                    for l in l_list:
                        if l < f_count:
                            item = QListWidgetItem("%s" % data[1][l])
                            if l == l_req:
                                item.setTextColor(QColor.red)
                            tag_widget.addItem(item)
                    lang_layout.addWidget(tag_widget)
        scroll.setWidget(widget)
        dialog.exec()

def get_platform_style():
    p = sys.platform
    n = "Courier"
    if p == "nt":
        n = "Consolas"
    elif p == "darwin":
        n = "Menlo"
    return "* {font-family: '%s';}" % n

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
        app.setStyleSheet(get_platform_style())
        widget = DirectoryWidget(filename)
        widget.setWindowTitle("SFNT Proofer")
        widget.setFixedSize(450, 400)
        widget.show()
        sys.exit(app.exec())
