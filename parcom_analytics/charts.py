"""Matplotlib charts shared by the dashboard and PDF output."""

from matplotlib.figure import Figure
from matplotlib.ticker import MaxNLocator

from .analytics import Analysis

ORANGE = "#e87926"
TEAL = "#285c63"


def draw_chart(figure: Figure, analysis: Analysis) -> None:
    figure.clear()
    axis = figure.add_subplot(111)
    figure.set_facecolor("white")
    axis.set_facecolor("white")
    values = analysis.chart
    axis.set_title(analysis.chart_title, loc="left", fontsize=11, color="#29343e", pad=14, weight="bold")
    if values.empty or (analysis.chart_kind != "histogram" and values.sum() == 0):
        axis.text(0.5, 0.5, "Keine auswertbaren Werte vorhanden", ha="center", va="center",
                  transform=axis.transAxes, color="#65727d")
        axis.set_axis_off()
    else:
        if analysis.chart_kind == "histogram":
            axis.hist(values, bins=min(12, max(1, len(values.unique()))), color=ORANGE, edgecolor="white")
            axis.set_xlabel("Minuten", fontsize=9, color="#65727d")
        else:
            colors = [ORANGE, TEAL] if analysis.kpi == 4 else ORANGE
            bars = axis.bar(range(len(values)), values.values, color=colors, width=0.65)
            step = max(1, (len(values) + 14) // 15) if analysis.chart_kind == "daily" else 1
            positions = list(range(0, len(values), step))
            axis.set_xticks(positions, [str(values.index[index]) for index in positions])
            if analysis.chart_kind != "daily":
                axis.bar_label(bars, padding=4, fontsize=9, color="#29343e")
                axis.margins(y=0.2)
            axis.set_xlabel("Tag" if analysis.chart_kind == "daily" else "", fontsize=9, color="#65727d")
        axis.set_ylabel("Anzahl Tickets", fontsize=9, color="#65727d")
        axis.yaxis.set_major_locator(MaxNLocator(integer=True))
        axis.set_axisbelow(True)
        axis.grid(axis="y", color="#e9edf0", linewidth=0.7)
        axis.tick_params(axis="both", labelsize=8, length=0, colors="#65727d", pad=7)
        for side in ["top", "right", "left"]:
            axis.spines[side].set_visible(False)
        axis.spines["bottom"].set_color("#dbe1e5")
    figure.subplots_adjust(left=0.07, right=0.98, bottom=0.23, top=0.80)
