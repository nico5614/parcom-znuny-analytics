"""Matplotlib charts shared by the dashboard and PDF output."""

from datetime import datetime
import math

from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter, MaxNLocator

from .analytics import Analysis, format_duration, format_value
from .reports import KpiReport, history_metrics
from .storage import month_label
from .service_desk import Report, history_series, score_status

ORANGE = "#e87926"
TEAL = "#285c63"
GRAY = "#98a3ad"
AMBER = "#d5a029"
RED = "#bf4943"
ROW_COLORS = {"attention": "#fff5dc", "critical": "#fcebea"}


def style_axis(axis):
    axis.set_facecolor("white")
    axis.set_axisbelow(True)
    axis.grid(axis="y", color="#e9edf0", linewidth=0.7)
    axis.tick_params(axis="both", labelsize=8, length=0, colors="#65727d", pad=7)
    for side in ["top", "right", "left"]:
        axis.spines[side].set_visible(False)
    axis.spines["bottom"].set_color("#dbe1e5")


def draw_chart(figure: Figure, analysis: Analysis) -> None:
    figure.clear()
    axis = figure.add_subplot(111)
    figure.set_facecolor("white")
    values = analysis.chart
    axis.set_title(analysis.chart_title, loc="left", fontsize=11, color="#29343e", pad=20, weight="bold")
    figure.subplots_adjust(left=0.08, right=0.98, bottom=0.24, top=0.73)
    if analysis.chart_kind == "donut":
        axis.set_title("", loc="left")
        figure.text(0.08, 0.88, analysis.chart_title, fontsize=11, color="#29343e", weight="bold")
        count, total = int(values.iloc[0]), int(values.sum())
        if total:
            axis.pie(values, colors=[RED, "#dfe4e8"], startangle=90, counterclock=False,
                     wedgeprops={"width": 0.29, "edgecolor": "white", "linewidth": 2})
        else:
            axis.pie([1], colors=["#edf0f2"], wedgeprops={"width": 0.29, "edgecolor": "white"})
        axis.text(0, 0.08, f'{format_value(analysis.references["escalation_rate"])} %',
                  ha="center", va="center", fontsize=21, weight="bold", color=RED if count else "#29343e")
        axis.text(0, -0.20, "Eskalationsquote", ha="center", fontsize=9, color="#65727d")
        axis.text(1.35, 0.3, f"{count} von {total} Tickets eskaliert", fontsize=12, weight="bold", color="#29343e")
        axis.text(1.35, -0.05, f"●  Eskaliert: {count}", color=RED, fontsize=10)
        axis.text(1.35, -0.35, f"●  Nicht eskaliert: {total-count}", color="#65727d", fontsize=10)
        axis.set_xlim(-1.5, 4.5)
        axis.set_ylim(-1.12, 1.15)
        axis.set_axis_off()
        figure.subplots_adjust(left=0.06, right=0.95, bottom=0.05, top=0.80)
        return
    if values.empty or (analysis.chart_kind != "histogram" and values.sum() == 0):
        axis.text(0.5, 0.5, "Keine auswertbaren Werte vorhanden", ha="center", va="center",
                  transform=axis.transAxes, color="#65727d")
        axis.set_axis_off()
        return
    if analysis.chart_kind == "histogram":
        axis.hist(values, bins=min(12, max(1, len(values.unique()))), color=ORANGE, edgecolor="white")
        median, mean = analysis.references["median"], analysis.references["mean"]
        axis.axvline(median, color=TEAL, linewidth=2, label=f"Median: {format_duration(median)}")
        axis.axvline(mean, color="#626a73", linestyle="--", linewidth=1.8, label=f"Durchschnitt: {format_duration(mean)}")
        axis.legend(loc="lower right", bbox_to_anchor=(1, 1.02), ncol=2, frameon=False, fontsize=9)
        axis.xaxis.set_major_locator(MaxNLocator(nbins=6, integer=True))
        axis.xaxis.set_major_formatter(FuncFormatter(lambda value, _: format_duration(max(0, value))))
        axis.set_xlim(left=0)
        axis.set_xlabel("Reaktionszeit" if analysis.kpi == 5 else "Lösungszeit", fontsize=9, color="#65727d")
    elif analysis.chart_kind == "daily":
        mean, maximum = analysis.references["daily_mean"], analysis.references["daily_max"]
        colors = ["#97430e" if value == maximum else "#c2611b" if value > mean else ORANGE for value in values]
        bars = axis.bar(range(len(values)), values.values, color=colors, width=0.65)
        axis.axhline(mean, color="#626a73", linestyle="--", linewidth=1.3,
                     label=f"Durchschnitt: {format_value(mean)} Tickets / Tag")
        axis.legend(loc="lower right", bbox_to_anchor=(1, 1.02), frameon=False, fontsize=9)
        for bar, value in zip(bars, values):
            if value == maximum:
                axis.annotate(f"{int(value)}", (bar.get_x()+bar.get_width()/2, value),
                              xytext=(0, 5), textcoords="offset points", ha="center", fontsize=9, weight="bold", color="#97430e")
        axis.text(0.0, 1.08, f"Höchstwert: {int(maximum)} Tickets", transform=axis.transAxes, fontsize=9, color="#97430e")
        positions = list(range(0, len(values), max(1, (len(values) + 14) // 15)))
        axis.set_xticks(positions, [str(values.index[index]) for index in positions])
        axis.set_xlabel("Tag · alle Kalendertage einschliesslich Tagen ohne Tickets", fontsize=9, color="#65727d")
        axis.margins(y=0.25)
    else:
        bars = axis.bar(range(len(values)), values.values,
                        color=[ORANGE, GRAY, AMBER, RED, "#dfe4e8"][:len(values)], width=0.6)
        axis.set_xticks(range(len(values)), values.index)
        axis.bar_label(bars, padding=4, fontsize=9, color="#29343e")
        axis.margins(y=0.25)
    axis.set_ylabel("Anzahl Tickets", fontsize=9, color="#65727d")
    axis.yaxis.set_major_locator(MaxNLocator(integer=True))
    style_axis(axis)


def draw_history(figure: Figure, report: KpiReport) -> None:
    figure.clear()
    figure.set_facecolor("white")
    axis = figure.add_subplot(111)
    metrics = history_metrics(report.analysis)
    finite_values = []
    for position, (name, (_, unit)) in enumerate(metrics.items()):
        values = [history_metrics(point.analysis)[name][0] if point.analysis else float("nan") for point in report.history]
        finite_values.extend(value for value in values if math.isfinite(value))
        axis.plot(range(len(values)), values, color=ORANGE if position == 0 else GRAY,
                  linewidth=2 if position == 0 else 1.5, marker="o", markersize=4, label=name)
    if not finite_values:
        axis.text(0.5, 0.5, "Keine auswertbaren historischen Werte vorhanden", ha="center", va="center", transform=axis.transAxes, color="#65727d")
        axis.set_axis_off()
        return
    count = len(report.history)
    ticks = sorted(set(range(0, count, max(1, (count + 5) // 6))) | {count-1})
    labels = []
    for index in ticks:
        record = report.history[index].record
        labels.append(month_label(record.reporting_month).replace(" ", "\n") if record.reporting_month
                      else datetime.fromisoformat(record.export_timestamp).strftime("%d.%m.%Y\n%H:%M"))
    axis.set_xticks(ticks, labels)
    axis.set_xlim(-0.35, max(0.35, count-0.65))
    unit = next(iter(metrics.values()))[1]
    if unit == "minutes":
        axis.yaxis.set_major_formatter(FuncFormatter(lambda value, _: format_duration(max(0, value))))
        axis.yaxis.set_major_locator(MaxNLocator(nbins=4, integer=True))
    elif unit == "percent":
        axis.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:g} %"))
    else:
        axis.yaxis.set_major_locator(MaxNLocator(integer=True, nbins=4))
    axis.set_ylim(0, max(1, max(finite_values) * 1.2))
    axis.legend(loc="lower left", bbox_to_anchor=(0, 1.01), ncol=2, frameon=False, fontsize=9)
    style_axis(axis)
    figure.subplots_adjust(left=0.16 if unit == "minutes" else 0.08, right=0.97, top=0.79, bottom=0.28)


def draw_score_history(figure: Figure, report: Report) -> None:
    figure.clear()
    series = history_series(report)
    if series.empty:
        return
    axis = figure.add_subplot(111)
    figure.subplots_adjust(left=0.07, right=0.97, top=0.88, bottom=0.22)
    for bottom, top, color in [(0, 60, "#bd3838"), (60, 75, "#e87926"),
                               (75, 90, "#d7c750"), (90, 100, "#23784c")]:
        axis.axhspan(bottom, top, color=color, alpha=0.08, linewidth=0)
    axis.plot(range(len(series)), series.values, color="#285c63", linewidth=2, marker="o", markersize=5)
    if report.current:
        index = len(series) - 1
        value = report.current.value
        axis.scatter([index], [value], color=score_status(value)[1], s=80, zorder=3, edgecolor="white")
        axis.annotate(f"{format_value(float(value))} %", (index, value), xytext=(0, 10), textcoords="offset points",
                      ha="center", color="#29343e", fontsize=10, fontweight="bold")
    axis.set_ylim(0, 108)
    axis.set_xlim(-0.5, len(series) - 0.5)
    axis.set_yticks([0, 60, 75, 90, 100], ["0 %", "60 %", "75 %", "90 %", "100 %"])
    # Keep long histories readable while preserving every plotted period.
    step = max(1, (len(series) + 7) // 8)
    ticks = sorted(set(range(0, len(series), step)) | {len(series) - 1})
    axis.set_xticks(ticks, [month_label(series.index[index]).replace(" ", "\n") for index in ticks])
    axis.tick_params(axis="both", length=0, labelsize=9, colors="#65727d", pad=8)
    axis.spines[["top", "right", "left", "bottom"]].set_visible(False)
    axis.grid(axis="y", color="white", linewidth=1)
