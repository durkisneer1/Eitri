"""VHDL token rules and QSyntaxHighlighter implementation."""
import re
from PySide6.QtGui import QColor, QSyntaxHighlighter, QTextCharFormat

KEYWORDS = set('''abs access after alias all and architecture array assert assume assume_guarantee
attribute begin block body buffer bus case component configuration constant context cover default
disconnect downto else elsif end entity exit fairness file for force function generate generic group
guarded if impure in inertial inout is label library linkage literal loop map mod nand new next nor
not null of on open or others out package parameter port postponed procedure process property
protected pure range record register reject release rem report restrict restrict_guarantee return
rol ror select sequence severity shared signal sla sll sra srl strong subtype then to transport type
unaffected units until use variable vmode vprop vunit wait when while with xnor xor'''.split())
TYPES = set('std_logic std_logic_vector std_ulogic std_ulogic_vector unsigned signed integer natural positive boolean bit bit_vector character string time real severity_level'.split())
TOKEN = re.compile(r'(?P<comment>--[^\n]*)|(?P<block>/\*)|(?P<string>"(?:[^"]|"")*"|\'[^\']\')|(?P<extended>\\[^\\]*\\)|(?P<number>\b\d[\w.#]*(?:[+-]\d+)?)|(?P<word>\b[a-zA-Z][\w]*\b)', re.IGNORECASE)


class VhdlHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)
        self.styles = {}
        for name, color in {'keyword': '#bba7c4', 'type': '#a9b9a1', 'string': '#c9bc91',
                            'number': '#c39e83', 'comment': '#928c81'}.items():
            style = QTextCharFormat()
            style.setForeground(QColor(color))
            if name == 'comment':
                style.setFontItalic(True)
            self.styles[name] = style

    def highlightBlock(self, text):
        # Qt offsets count UTF-16 units, unlike Python's Unicode code points.
        def paint(start, end, kind):
            offset = len(text[:start].encode('utf-16-le')) // 2
            length = len(text[start:end].encode('utf-16-le')) // 2
            self.setFormat(offset, length, self.styles[kind])

        self.setCurrentBlockState(0)
        position = 0
        if self.previousBlockState() == 1:
            end = text.find('*/')
            if end < 0:
                paint(0, len(text), 'comment')
                self.setCurrentBlockState(1)
                return
            position = end + 2
            paint(0, position, 'comment')
        while match := TOKEN.search(text, position):
            position = match.end()
            kind = match.lastgroup
            if kind == 'block':
                end = text.find('*/', position)
                position = len(text) if end < 0 else end + 2
                paint(match.start(), position, 'comment')
                if end < 0:
                    self.setCurrentBlockState(1)
            elif kind == 'word':
                word = match.group().lower()
                if word in KEYWORDS:
                    paint(match.start(), position, 'keyword')
                elif word in TYPES:
                    paint(match.start(), position, 'type')
            elif kind in self.styles:
                paint(match.start(), position, kind)


