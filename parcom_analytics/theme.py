"""Dark desktop palette; printed reports retain their light background."""

from pathlib import Path

from matplotlib.colors import to_hex

ASSETS = Path(__file__).resolve().parent.parent / "assets"
APP_LOGO = ASSETS / ("app_logo_dark.png" if (ASSETS / "app_logo_dark.png").exists() else "app_logo.png")
APP_ICON = ASSETS / ("app_icon.ico" if (ASSETS / "app_icon.ico").exists() else "app_logo.png")
BACKGROUND = "#08111B"
CARD = "#101C29"
TEXT = "#F4F7FA"
MUTED = "#A6B2BF"
DARK_ROW_COLORS = {"attention": "#403720", "critical": "#452b30"}
DARK_SCORE_COLORS = {"#23784c": "#39E58C", "#8a7300": "#FFB84D", "#b85b0b": "#FFB84D", "#bd3838": "#FF5C6C"}

STYLE = """
QWidget { color: #F4F7FA; font-size: 13px; }
QMainWindow, QWidget#shell, QWidget#page { background: #08111B; }
QFrame#sidebar { background: #0B1520; border-right: 1px solid #203247; }
QFrame#header { background: #08111B; }
QFrame#card { background: #101C29; border: 1px solid #203247; border-radius: 12px; }
QLabel { background: transparent; border: none; }
QLabel#brand { font-size: 18px; font-weight: 600; }
QLabel#title { font-size: 30px; font-weight: 600; }
QLabel#section { font-size: 20px; font-weight: 600; }
QLabel#muted { color: #A6B2BF; }
QLabel#eyebrow { color: #efa567; font-size: 12px; font-weight: 600; }
QLabel#metric { color: #f0f3f6; font-size: 52px; font-weight: 600; }
QLabel#warning { background: #3b3023; color: #f0c28b; border-radius: 6px; padding: 8px; }
QPushButton { background: #FF6B2C; color: #111820; border: 1px solid transparent; border-radius: 7px; padding: 10px 16px; font-weight: 600; }
QPushButton:hover { background: #f09249; }
QPushButton:focus { border: 1px solid #f6b887; }
QPushButton:disabled { background: #2d3540; color: #8f9aaa; }
QPushButton#nav, QPushButton#secondary { background: transparent; color: #afbbc9; text-align: left; }
QPushButton#nav:hover, QPushButton#secondary:hover { background: #142333; }
QPushButton#nav { min-height: 24px; font-size: 14px; }
QPushButton#nav:checked { background: #182A38; color: #32D5FF; border-left: 3px solid #FF6B2C; }
QComboBox, QLineEdit, QDateTimeEdit, QDateEdit { background: #101C29; color: #F4F7FA; border: 1px solid #203247; border-radius: 7px; padding: 9px; }
QComboBox:focus, QLineEdit:focus, QDateTimeEdit:focus, QDateEdit:focus { border: 1px solid #FF6B2C; }
QComboBox::drop-down { border: none; width: 24px; }
QComboBox::down-arrow { image: url(__ARROW__); width: 12px; height: 8px; }
QComboBox QAbstractItemView { background: #142333; color: #F4F7FA; selection-background-color: #182A38; selection-color: #32D5FF; padding: 5px; }
QTableView { font-size: 13px; background: #101C29; alternate-background-color: #142333; color: #F4F7FA; border: none; gridline-color: #203247; selection-background-color: #414d5c; selection-color: white; }
QHeaderView::section { font-size: 12px; background: #142333; color: #b8c3cf; padding: 9px; border: none; border-bottom: 1px solid #203247; font-weight: 600; }
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { background: #08111B; width: 10px; }
QScrollBar::handle:vertical { background: #465363; min-height: 25px; border-radius: 4px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QProgressBar { background: #142333; border: none; border-radius: 3px; color: #F4F7FA; text-align: center; min-height: 6px; }
QProgressBar::chunk { background: #FF6B2C; border-radius: 3px; }
QCheckBox { spacing: 10px; }
QToolTip { background: #142333; color: #F4F7FA; border: 1px solid #536171; padding: 6px; }
QMessageBox, QDialog, QCalendarWidget { background: #101C29; }
""".replace("__ARROW__", (ASSETS / "chevron.svg").as_posix())


def dark_figure(figure):
    figure.set_facecolor(CARD)
    colors = {"#29343e": TEXT, "#65727d": MUTED, "#626a73": MUTED,
              "#285c63": "#77bfc2", "#97430e": "#FFB84D", "#bf4943": "#e7837c"}
    for axis in figure.axes:
        axis.set_facecolor(CARD)
        axis.tick_params(colors=MUTED)
        for spine in axis.spines.values():
            spine.set_color("#203247")
        for line in axis.get_ygridlines():
            line.set_color("#35404d")
        for line in axis.lines:
            old = to_hex(line.get_color())
            if old in colors:
                line.set_color(colors[old])
    from matplotlib.patches import Wedge
    accents = {"#e87926": "#32D5FF", "#c2611b": "#4C8DFF", "#97430e": "#8B6CFF",
               "#98a3ad": "#4C8DFF", "#dfe4e8": "#203247", "#bf4943": "#FF5C6C",
               "#d5a029": "#FFB84D"}
    for axis in figure.axes:
        for patch in axis.patches:
            old = to_hex(patch.get_facecolor())
            if old in accents:
                patch.set_facecolor(accents[old])
            if isinstance(patch, Wedge):
                patch.set_edgecolor(CARD)
    from matplotlib.text import Text
    for text in figure.findobj(Text):
        old = to_hex(text.get_color())
        text.set_color(colors.get(old, MUTED if old == "#000000" else old))


def application_font():
    from PySide6.QtGui import QFont, QFontDatabase
    installed = set(QFontDatabase.families())
    for family in ("Frutiger Neue LT Pro Light", "Segoe UI Variable", "Segoe UI"):
        if family in installed:
            return QFont(family, 10)
    return QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont)
