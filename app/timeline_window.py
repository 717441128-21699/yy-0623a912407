from datetime import datetime, timedelta
from typing import Optional, Dict, List

from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QColor, QPainter, QPen, QFont, QBrush, QPainterPath
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea,
    QFrame, QSizePolicy, QGraphicsDropShadowEffect, QCheckBox
)

from .models import (
    TransportRecord, AlertType, AlertSeverity, TemperatureReading,
    ResponsibilityPhase
)


ALERT_COLORS = {
    AlertSeverity.CRITICAL: "#E53935",
    AlertSeverity.WARNING: "#FB8C00",
    AlertSeverity.INFO: "#1E88E5",
}

ALERT_ICON = {
    AlertType.POWER_DISCONNECT: "⚡",
    AlertType.COOLER_STOP: "❄",
    AlertType.TEMP_EXCEED: "🌡",
    AlertType.DRIVER_CONFIRM: "👤",
    AlertType.POWER_RESTORE: "🔌",
    AlertType.COOLER_RESTART: "❄",
    AlertType.TEMP_RECOVER: "✓",
    AlertType.LOADING: "📦",
    AlertType.UNLOADING: "🏁",
}


PHASE_STYLES = {
    ResponsibilityPhase.LOADING_SEAL: ("#2E7D32", "#E8F5E9", "📦", "装货封签"),
    ResponsibilityPhase.DEPARTURE_POWER: ("#1565C0", "#E3F2FD", "🚚", "出发切换冷源"),
    ResponsibilityPhase.EQUIPMENT_FAULT: ("#C62828", "#FFEBEE", "⚠", "设备故障"),
    ResponsibilityPhase.DRIVER_RESPONSE: ("#E65100", "#FFF3E0", "👤", "司机响应"),
    ResponsibilityPhase.MAINTENANCE_RECOVERY: ("#6A1B9A", "#F3E5F5", "🔧", "维修恢复"),
    ResponsibilityPhase.NORMAL_TRANSIT: ("#455A64", "#ECEFF1", "🛣", "后续在途"),
    ResponsibilityPhase.ARRIVAL_ACCEPTANCE: ("#00695C", "#E0F2F1", "🏁", "到货验收"),
}


def _phase_color(phase: ResponsibilityPhase):
    return PHASE_STYLES.get(phase, ("#546E7A", "#F5F5F5", "●", ""))[0]


def _phase_bg(phase: ResponsibilityPhase):
    return PHASE_STYLES.get(phase, ("#546E7A", "#F5F5F5", "●", ""))[1]


def _phase_icon(phase: ResponsibilityPhase):
    return PHASE_STYLES.get(phase, ("#546E7A", "#F5F5F5", "●", ""))[2]


def _phase_title(phase: ResponsibilityPhase):
    return PHASE_STYLES.get(phase, ("#546E7A", "#F5F5F5", "●", phase.value))[3] + "阶段"


class TimelineWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._record: Optional[TransportRecord] = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        header = self._build_header()
        layout.addWidget(header)

        body = QHBoxLayout()
        body.setSpacing(14)

        left_panel = self._build_timeline_panel()
        body.addWidget(left_panel, 5)

        right_panel = self._build_chart_panel()
        body.addWidget(right_panel, 7)

        body_widget = QWidget()
        body_widget.setLayout(body)
        layout.addWidget(body_widget, 1)

    def _build_header(self) -> QWidget:
        container = QFrame()
        container.setObjectName("timelineHeader")
        container.setProperty("role", "panel")
        layout = QHBoxLayout(container)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(24)

        self.lbl_summary = QLabel("尚未导入运输记录")
        self.lbl_summary.setObjectName("timelineSummary")
        self.lbl_summary.setWordWrap(True)

        stats_container = QHBoxLayout()
        stats_container.setSpacing(20)

        self.stat_critical = self._make_stat("严重告警", "0", "#E53935")
        self.stat_warning = self._make_stat("一般告警", "0", "#FB8C00")
        self.stat_info = self._make_stat("一般事件", "0", "#1E88E5")

        stats_container.addLayout(self.stat_critical["layout"])
        stats_container.addLayout(self.stat_warning["layout"])
        stats_container.addLayout(self.stat_info["layout"])

        layout.addWidget(self.lbl_summary, 1)
        layout.addLayout(stats_container)

        return container

    def _make_stat(self, label: str, value: str, color: str) -> dict:
        wrap = QVBoxLayout()
        wrap.setSpacing(2)
        lbl_val = QLabel(value)
        lbl_val.setObjectName("statValue")
        lbl_val.setStyleSheet(f"color: {color};")
        lbl_val.setAlignment(Qt.AlignCenter)
        lbl_lab = QLabel(label)
        lbl_lab.setObjectName("statLabel")
        lbl_lab.setAlignment(Qt.AlignCenter)
        wrap.addWidget(lbl_val)
        wrap.addWidget(lbl_lab)
        return {"layout": wrap, "value": lbl_val, "label": lbl_lab}

    def _build_timeline_panel(self) -> QWidget:
        container = QFrame()
        container.setProperty("role", "panel")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        title_wrap = QHBoxLayout()
        title_wrap.setContentsMargins(0, 0, 0, 0)

        title_bar = QLabel("  告警时间轴（按分钟排列）")
        title_bar.setObjectName("panelTitle")
        title_bar.setFixedHeight(40)

        self.chk_group = QCheckBox("按责任链分组")
        self.chk_group.setChecked(True)
        self.chk_group.setCursor(Qt.PointingHandCursor)
        self.chk_group.setStyleSheet(
            "QCheckBox { padding: 0 14px 0 0; color: #1976D2; font-weight: 600; }"
            "QCheckBox::indicator { width: 13px; height: 13px; border-radius: 3px; }"
        )
        self.chk_group.stateChanged.connect(lambda _=0: self._render_timeline())

        title_wrap.addWidget(title_bar, 1)
        title_wrap.addWidget(self.chk_group, 0, Qt.AlignVCenter)

        title_wrap_w = QWidget()
        title_wrap_w.setLayout(title_wrap)
        title_wrap_w.setObjectName("panelTitle")
        title_wrap_w.setStyleSheet("#panelTitle { background: #F8FAFC; border-bottom: 1px solid #ECEFF3; border-top-left-radius: 8px; border-top-right-radius: 8px; }")
        title_wrap_w.setFixedHeight(40)
        layout.addWidget(title_wrap_w)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)

        self.timeline_widget = QWidget()
        self.timeline_layout = QVBoxLayout(self.timeline_widget)
        self.timeline_layout.setContentsMargins(14, 14, 14, 14)
        self.timeline_layout.setSpacing(4)
        self.timeline_layout.addStretch(1)

        self.scroll.setWidget(self.timeline_widget)
        layout.addWidget(self.scroll, 1)

        return container

    def _build_chart_panel(self) -> QWidget:
        container = QFrame()
        container.setProperty("role", "panel")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        title_bar = QLabel("  温度趋势概览")
        title_bar.setObjectName("panelTitle")
        title_bar.setFixedHeight(40)
        layout.addWidget(title_bar)

        self.chart = TemperatureChart()
        layout.addWidget(self.chart, 1)

        self.legend = QLabel()
        self.legend.setObjectName("chartLegend")
        self.legend.setContentsMargins(12, 6, 12, 8)
        self.legend.setWordWrap(True)
        layout.addWidget(self.legend)

        return container

    def set_record(self, record: TransportRecord):
        self._record = record
        self._render_timeline()
        self._render_summary()
        self.chart.set_record(record)
        self._render_chart_legend()

    def _render_summary(self):
        if not self._record:
            self.lbl_summary.setText("尚未导入运输记录")
            return
        r = self._record
        duration = (r.arrival_time - r.departure_time) if r.arrival_time else timedelta(0)
        hours, rem = divmod(duration.total_seconds(), 3600)
        mins = rem // 60
        text = (
            f"<b>{r.record_id}</b>  |  车牌 {r.vehicle_plate}  |  司机 {r.driver_name}<br>"
            f"路线：{r.route_from} → {r.route_to}<br>"
            f"出发 {r.departure_time.strftime('%m-%d %H:%M')}  "
            f"到达 {r.arrival_time.strftime('%m-%d %H:%M') if r.arrival_time else '—'}  "
            f"（行程约 {int(hours)}h{int(mins)}min）"
        )
        self.lbl_summary.setText(text)

        alerts = self._record.alerts
        c = sum(1 for a in alerts if a.severity == AlertSeverity.CRITICAL)
        w = sum(1 for a in alerts if a.severity == AlertSeverity.WARNING)
        i = sum(1 for a in alerts if a.severity == AlertSeverity.INFO)
        self.stat_critical["value"].setText(str(c))
        self.stat_warning["value"].setText(str(w))
        self.stat_info["value"].setText(str(i))

    def _render_timeline(self):
        while self.timeline_layout.count():
            item = self.timeline_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        if not self._record:
            empty = QLabel("请先导入运输记录。点击工具栏「导入示例数据」或「加载运输记录文件」。")
            empty.setObjectName("emptyHint")
            empty.setWordWrap(True)
            empty.setAlignment(Qt.AlignCenter)
            self.timeline_layout.addWidget(empty)
            self.timeline_layout.addStretch(1)
            return

        if self.chk_group.isChecked():
            grouped = self._record.group_alerts_by_responsibility()
            phase_list = list(grouped.keys())
            for pidx, phase in enumerate(phase_list):
                alerts_in_phase = grouped[phase]
                if not alerts_in_phase:
                    continue
                banner = self._make_phase_banner(phase, alerts_in_phase)
                self.timeline_layout.addWidget(banner)
                for idx, alert in enumerate(alerts_in_phase):
                    is_phase_first = (idx == 0) and (pidx == 0)
                    is_phase_last = (idx == len(alerts_in_phase) - 1) and (pidx == len(phase_list) - 1)
                    node = self._make_timeline_node(
                        alert, is_phase_first, is_phase_last, phase,
                        is_group_first=(idx == 0),
                        is_group_last=(idx == len(alerts_in_phase) - 1),
                    )
                    self.timeline_layout.addWidget(node)
        else:
            for idx, alert in enumerate(self._record.sorted_alerts()):
                node = self._make_timeline_node(alert, idx == 0, idx == len(self._record.alerts) - 1, None)
                self.timeline_layout.addWidget(node)

        self.timeline_layout.addStretch(1)

    def _make_phase_banner(self, phase: ResponsibilityPhase, alerts: list) -> QWidget:
        container = QWidget()
        container.setMinimumHeight(38)
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 8, 0, 4)
        layout.setSpacing(8)

        icon_lbl = QLabel(_phase_icon(phase))
        icon_lbl.setFixedSize(28, 28)
        icon_lbl.setAlignment(Qt.AlignCenter)
        color = _phase_color(phase)
        bg = _phase_bg(phase)
        icon_lbl.setStyleSheet(
            f"border-radius: 14px; background: {bg}; color: {color};"
            f" font-size: 14px; font-weight: bold; border: 1px solid {color}66;"
        )

        title_wrap = QVBoxLayout()
        title_wrap.setSpacing(0)
        title_lbl = QLabel(_phase_title(phase))
        title_lbl.setStyleSheet(f"color: {color}; font-size: 13px; font-weight: 700;")
        times = [a.timestamp for a in alerts]
        t_start = min(times).strftime("%H:%M")
        t_end = max(times).strftime("%H:%M")
        count = len(alerts)
        subtitle_text = f"{t_start} ~ {t_end}　共 {count} 个节点"
        if phase == ResponsibilityPhase.DRIVER_RESPONSE:
            cooler = [a for a in alerts if a.alert_type.name == "COOLER_STOP"]
            confirm = [a for a in alerts if a.alert_type.name == "DRIVER_CONFIRM"]
            if not cooler:
                all_alerts = self._record.sorted_alerts()
                cooler = [a for a in all_alerts if a.alert_type.name == "COOLER_STOP"]
            if cooler and confirm:
                lag = (confirm[0].timestamp - cooler[0].timestamp).total_seconds() / 60
                subtitle_text += f"　响应延迟 {lag:.0f} 分钟"
        elif phase == ResponsibilityPhase.MAINTENANCE_RECOVERY:
            all_alerts = self._record.sorted_alerts()
            cooler = [a for a in all_alerts if a.alert_type.name == "COOLER_STOP"]
            restore = [a for a in all_alerts if a.alert_type.name in ("POWER_RESTORE", "COOLER_RESTART")]
            if cooler and restore:
                lag = (restore[0].timestamp - cooler[0].timestamp).total_seconds() / 60
                subtitle_text += f"　停机 → 恢复 {lag:.0f} 分钟"
        sub_lbl = QLabel(subtitle_text)
        sub_lbl.setStyleSheet("color: #546E7A; font-size: 11px;")
        title_wrap.addWidget(title_lbl)
        title_wrap.addWidget(sub_lbl)

        layout.addWidget(icon_lbl, 0, Qt.AlignVCenter)
        layout.addLayout(title_wrap, 1)
        layout.addStretch(1)

        left_bar = QFrame()
        left_bar.setFixedWidth(3)
        left_bar.setStyleSheet(f"background: {color}; border-radius: 2px;")
        wrapper = QHBoxLayout()
        wrapper.setContentsMargins(0, 0, 0, 0)
        wrapper.setSpacing(8)
        wrap_widget = QWidget()
        wrap_widget.setLayout(wrapper)
        wrapper.addWidget(left_bar)
        wrapper.addWidget(container, 1)
        wrap_widget.setStyleSheet(f"background: {bg}33; border-radius: 6px; padding: 2px 4px;")
        return wrap_widget

    def _make_timeline_node(
        self, alert, is_first: bool, is_last: bool,
        phase: Optional[ResponsibilityPhase] = None,
        is_group_first: bool = False,
        is_group_last: bool = False,
    ) -> QWidget:
        container = QWidget()
        container.setMinimumHeight(74)
        root_layout = QHBoxLayout(container)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(10)

        color = ALERT_COLORS[alert.severity]
        icon = ALERT_ICON.get(alert.alert_type, "●")

        rail_color = "#E0E4EA"
        if phase is not None:
            rail_color = _phase_color(phase) + "99"

        rail_layout = QVBoxLayout()
        rail_layout.setContentsMargins(6, 0, 6, 0)
        rail_layout.setSpacing(0)

        top_transparent = is_first or (phase is not None and is_group_first)
        bottom_transparent = is_last or (phase is not None and is_group_last)

        line_top = QFrame()
        line_top.setFixedWidth(2)
        line_top.setStyleSheet(f"background: {'transparent' if top_transparent else rail_color};")
        line_top.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)

        dot = QLabel(icon)
        dot.setAlignment(Qt.AlignCenter)
        dot.setFixedSize(30, 30)
        dot.setStyleSheet(
            f"border-radius: 15px; background: {color}; color: white;"
            f" font-size: 14px; font-weight: bold;"
        )
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(8)
        shadow.setColor(QColor(0, 0, 0, 40))
        shadow.setOffset(0, 2)
        dot.setGraphicsEffect(shadow)

        line_bottom = QFrame()
        line_bottom.setFixedWidth(2)
        line_bottom.setStyleSheet(f"background: {'transparent' if bottom_transparent else rail_color};")
        line_bottom.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)

        rail_layout.addWidget(line_top, 1)
        rail_layout.addWidget(dot, 0, Qt.AlignCenter)
        rail_layout.addWidget(line_bottom, 1)

        root_layout.addLayout(rail_layout)

        content = QFrame()
        content.setProperty("role", "timelineCard")
        content.setStyleSheet(
            f"QFrame[role='timelineCard'] {{ border-left: 3px solid {color};"
            f" background: #FAFBFC; padding: 10px; border-radius: 4px; }}"
        )
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(10, 8, 10, 8)
        content_layout.setSpacing(4)

        top_row = QHBoxLayout()
        time_label = QLabel(alert.timestamp.strftime("%m-%d %H:%M"))
        time_label.setObjectName("alertTime")
        type_label = QLabel(f"[{alert.alert_type.value}]")
        type_label.setObjectName("alertType")
        type_label.setStyleSheet(f"color: {color};")
        temp_text = ""
        if alert.temperature is not None:
            temp_text = f"<span style='color:#546E7A; font-weight:600;'> {alert.temperature:.1f}℃</span>"
        top_row.addWidget(time_label)
        top_row.addWidget(type_label)
        top_row.addSpacing(8)
        if temp_text:
            temp_lbl = QLabel(temp_text)
            temp_lbl.setTextFormat(Qt.RichText)
            top_row.addWidget(temp_lbl)
        top_row.addStretch(1)
        content_layout.addLayout(top_row)

        desc_label = QLabel(alert.description)
        desc_label.setObjectName("alertDesc")
        desc_label.setWordWrap(True)
        content_layout.addWidget(desc_label)

        meta_parts = []
        if alert.operator:
            meta_parts.append(f"操作人：{alert.operator}")
        if alert.location:
            meta_parts.append(f"地点：{alert.location}")
        if meta_parts:
            meta_label = QLabel("    ".join(meta_parts))
            meta_label.setObjectName("alertMeta")
            content_layout.addWidget(meta_label)

        root_layout.addWidget(content, 1)

        return container

    def _render_chart_legend(self):
        if not self._record or not self._record.cargo:
            self.legend.setText("提示：温区范围由「温区影响估算」面板中填写的货品配置决定。")
            return
        c = self._record.cargo
        text = (
            f"约定温区：<b style='color:#1E88E5;'>{c.temp_min:.1f}℃ ~ {c.temp_max:.1f}℃</b>　　"
            f"容忍越线时长：<b>{c.tolerance_minutes} 分钟</b>　　"
            f"货品：{c.cargo_name}"
        )
        self.legend.setText(text)
        self.legend.setTextFormat(Qt.RichText)


class TemperatureChart(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._record: Optional[TransportRecord] = None
        self.setMinimumHeight(260)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_record(self, record: TransportRecord):
        self._record = record
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self.rect().adjusted(48, 16, 16, 36)
        w, h = rect.width(), rect.height()

        painter.fillRect(self.rect(), QColor("#FFFFFF"))
        self._draw_grid(painter, rect)
        self._draw_temp_band(painter, rect)
        self._draw_curve(painter, rect)
        self._draw_alert_markers(painter, rect)
        self._draw_axes_labels(painter, rect)

    def _draw_grid(self, painter, rect):
        pen = QPen(QColor("#EEF1F5"))
        pen.setWidth(1)
        painter.setPen(pen)
        for i in range(5):
            y = rect.top() + rect.height() * i / 4
            painter.drawLine(rect.left(), y, rect.right(), y)
        for i in range(6):
            x = rect.left() + rect.width() * i / 5
            painter.drawLine(x, rect.top(), x, rect.bottom())

    def _get_temp_range(self):
        if not self._record:
            return (-28, -8)
        temps = [r.temperature for r in self._record.temperature_log]
        if self._record.cargo:
            temps += [self._record.cargo.temp_min, self._record.cargo.temp_max]
        tmin = min(temps) - 2
        tmax = max(temps) + 2
        return (tmin, tmax)

    def _get_time_range(self):
        if not self._record:
            base = datetime.now()
            return (base, base + timedelta(hours=5))
        start = self._record.departure_time
        end = self._record.unloading_time or self._record.arrival_time or (start + timedelta(hours=5))
        if end <= start:
            end = start + timedelta(hours=1)
        return (start, end)

    def _draw_temp_band(self, painter, rect):
        if not self._record or not self._record.cargo:
            return
        tmin, tmax = self._get_temp_range()
        cmin, cmax = self._record.cargo.temp_min, self._record.cargo.temp_max
        span = tmax - tmin
        if span <= 0:
            return
        y_top = rect.top() + rect.height() * (1 - (cmax - tmin) / span)
        y_bot = rect.top() + rect.height() * (1 - (cmin - tmin) / span)
        band_rect = QRectF(rect.left(), y_top, rect.width(), y_bot - y_top)
        painter.fillRect(band_rect, QColor(30, 136, 229, 28))
        pen = QPen(QColor(30, 136, 229, 120))
        pen.setWidth(1)
        pen.setStyle(Qt.DashLine)
        painter.setPen(pen)
        painter.drawLine(rect.left(), y_top, rect.right(), y_top)
        painter.drawLine(rect.left(), y_bot, rect.right(), y_bot)

    def _draw_curve(self, painter, rect):
        if not self._record or not self._record.temperature_log:
            return
        tmin, tmax = self._get_temp_range()
        t_start, t_end = self._get_time_range()
        temp_span = tmax - tmin
        time_span = (t_end - t_start).total_seconds()
        if temp_span <= 0 or time_span <= 0:
            return

        points = []
        exceeded_points = []
        cmin, cmax = (
            (self._record.cargo.temp_min, self._record.cargo.temp_max)
            if self._record.cargo else (None, None)
        )

        for reading in self._record.temperature_log:
            rx = (reading.timestamp - t_start).total_seconds() / time_span
            if rx < 0 or rx > 1:
                continue
            x = rect.left() + rect.width() * rx
            ry = 1 - (reading.temperature - tmin) / temp_span
            y = rect.top() + rect.height() * ry
            p = QPointF(x, y)
            points.append(p)
            if cmin is not None and (reading.temperature < cmin or reading.temperature > cmax):
                exceeded_points.append(p)

        if len(points) < 2:
            return

        path = QPainterPath()
        path.moveTo(points[0])
        for p in points[1:]:
            path.lineTo(p)

        pen = QPen(QColor(46, 125, 50))
        pen.setWidth(2)
        painter.setPen(pen)
        painter.drawPath(path)

        if exceeded_points:
            pen2 = QPen(QColor(229, 57, 53))
            pen2.setWidth(3)
            painter.setPen(pen2)
            for p in exceeded_points[::5]:
                painter.drawEllipse(p, 2.5, 2.5)

    def _draw_alert_markers(self, painter, rect):
        if not self._record:
            return
        t_start, t_end = self._get_time_range()
        time_span = (t_end - t_start).total_seconds()
        if time_span <= 0:
            return
        critical_alerts = [a for a in self._record.alerts if a.severity == AlertSeverity.CRITICAL]
        for alert in critical_alerts:
            rx = (alert.timestamp - t_start).total_seconds() / time_span
            if rx < 0 or rx > 1:
                continue
            x = rect.left() + rect.width() * rx
            color = ALERT_COLORS[alert.severity]
            pen = QPen(QColor(color))
            pen.setWidth(2)
            pen.setStyle(Qt.SolidLine)
            painter.setPen(pen)
            painter.drawLine(x, rect.top(), x, rect.bottom())
            painter.fillRect(QRectF(x - 4, rect.top() - 4, 8, 8), QColor(color))

    def _draw_axes_labels(self, painter, rect):
        tmin, tmax = self._get_temp_range()
        painter.setPen(QColor("#6B7280"))
        painter.setFont(QFont("Microsoft YaHei", 8))
        for i in range(5):
            y = rect.top() + rect.height() * i / 4
            temp_val = tmax - (tmax - tmin) * i / 4
            painter.drawText(2, y + 4, 44, 16, Qt.AlignRight | Qt.AlignVCenter, f"{temp_val:.0f}℃")

        t_start, t_end = self._get_time_range()
        for i in range(6):
            x = rect.left() + rect.width() * i / 5
            ratio = i / 5
            t = t_start + (t_end - t_start) * ratio
            painter.drawText(
                x - 28, rect.bottom() + 8, 56, 20,
                Qt.AlignCenter, t.strftime("%H:%M")
            )
