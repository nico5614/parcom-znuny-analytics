"""Dark desktop palette; printed reports retain their light background."""

from pathlib import Path

from matplotlib.colors import to_hex

ASSETS = Path(__file__).resolve().parent.parent / "assets"
APP_LOGO = ASSETS / ("app_logo_dark.png" if (ASSETS / "app_logo_dark.png").exists() else "app_logo.png")
APP_ICON = ASSETS / ("app_icon.ico" if (ASSETS / "app_icon.ico").exists() else "app_logo.png")
BACKGROUND = "#14181f"
CARD = "#20262f"
TEXT = "#e7ebef"
MUTED = "#a2afbe"
DARK_ROW_COLORS = {"attention": "#403720", "critical": "#452b30"}
DARK_SCORE_COLORS = {"#23784c": "#59bd8b", "#8a7300": "#d4b15f", "#b85b0b": "#f0a96f", "#bd3838": "#e08181"}

STYLE = """
QWidget { color: #e7ebef; font-family: 'Segoe UI'; font-size: 13px; }
QMainWindow, QWidget#shell, QWidget#page { background: #14181f; }
QFrame#sidebar { background: #10141a; border-right: 1px solid #2b3340; }
QFrame#header { background: #14181f; }
QFrame#card { background: #20262f; border: 1px solid #303946; border-radius: 12px; }
QLabel { background: transparent; border: none; }
QLabel#brand { font-size: 18px; font-weight: 600; }
QLabel#title { font-size: 26px; font-weight: 600; }
QLabel#section { font-size: 14px; font-weight: 600; }
QLabel#muted { color: #a2afbe; }
QLabel#eyebrow { color: #efa567; font-size: 12px; font-weight: 600; }
QLabel#metric { color: #f0f3f6; font-size: 29px; font-weight: 600; }
QLabel#warning { background: #3b3023; color: #f0c28b; border-radius: 6px; padding: 8px; }
QPushButton { background: #e87926; color: #111820; border: 1px solid transparent; border-radius: 7px; padding: 10px 16px; font-weight: 600; }
QPushButton:hover { background: #f09249; }
QPushButton:focus { border: 1px solid #f6b887; }
QPushButton:disabled { background: #2d3540; color: #8f9aaa; }
QPushButton#nav, QPushButton#secondary { background: transparent; color: #afbbc9; text-align: left; }
QPushButton#nav:hover, QPushButton#secondary:hover { background: #242c36; }
QPushButton#nav:checked { background: #473020; color: #ffb276; border-left: 3px solid #e87926; }
QComboBox, QLineEdit, QDateEdit { background: #20262f; color: #e7ebef; border: 1px solid #3b4655; border-radius: 7px; padding: 9px; }
QComboBox:focus, QLineEdit:focus, QDateEdit:focus { border: 1px solid #e87926; }
QComboBox::drop-down { border: none; width: 24px; }
QComboBox::down-arrow { image: url(__ARROW__); width: 12px; height: 8px; }
QComboBox QAbstractItemView { background: #242c36; color: #e7ebef; selection-background-color: #473020; selection-color: #ffb276; padding: 5px; }
QTableView { background: #20262f; alternate-background-color: #242c36; color: #e7ebef; border: none; gridline-color: #303946; selection-background-color: #414d5c; selection-color: white; }
QHeaderView::section { background: #29323e; color: #b8c3cf; padding: 9px; border: none; border-bottom: 1px solid #3b4655; font-weight: 600; }
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { background: #14181f; width: 10px; }
QScrollBar::handle:vertical { background: #465363; min-height: 25px; border-radius: 4px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QProgressBar { background: #29323e; border: none; border-radius: 3px; color: #e7ebef; text-align: center; min-height: 6px; }
QProgressBar::chunk { background: #e87926; border-radius: 3px; }
QCheckBox { spacing: 10px; }
QToolTip { background: #29323e; color: #e7ebef; border: 1px solid #536171; padding: 6px; }
QMessageBox, QDialog, QCalendarWidget { background: #20262f; }
""".replace("__ARROW__", (ASSETS / "chevron.svg").as_posix())


def dark_figure(figure):
    figure.set_facecolor(CARD)
    colors = {"#29343e": TEXT, "#65727d": MUTED, "#626a73": MUTED,
              "#285c63": "#77bfc2", "#97430e": "#f0a96f", "#bf4943": "#e7837c"}
    for axis in figure.axes:
        axis.set_facecolor(CARD)
        axis.tick_params(colors=MUTED)
        for spine in axis.spines.values():
            spine.set_color("#3b4655")
        for line in axis.get_ygridlines():
            line.set_color("#35404d")
        for line in axis.lines:
            old = to_hex(line.get_color())
            if old in colors:
                line.set_color(colors[old])
    from matplotlib.text import Text
    for text in figure.findobj(Text):
        old = to_hex(text.get_color())
        text.set_color(colors.get(old, MUTED if old == "#000000" else old))
