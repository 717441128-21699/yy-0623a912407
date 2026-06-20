import json
import pickle
from datetime import datetime, timedelta
from typing import Optional

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QAction
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTabWidget,
    QToolBar, QFileDialog, QMessageBox, QStatusBar, QPushButton,
    QFrame, QSizePolicy
)

from .models import TransportRecord
from .sample_data import generate_sample_record
from .timeline_window import TimelineWindow
from .impact_window import ImpactWindow
from .export_window import ExportWindow


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._record: Optional[TransportRecord] = None
        self._build_window()
        self._build_toolbar()
        self._build_central()
        self._build_statusbar()
        self._apply_initial_hint()

    def _build_window(self):
        self.setWindowTitle("冷藏车断电复盘工具 · Cold Chain Review")
        self.setMinimumSize(1280, 780)
        self.resize(1440, 880)

    def _build_toolbar(self):
        tb = QToolBar("主工具栏", self)
        tb.setObjectName("mainToolbar")
        tb.setIconSize(QSize(18, 18))
        tb.setMovable(False)
        tb.setAllowedAreas(Qt.TopToolBarArea)
        self.addToolBar(tb)

        spacer_left = QWidget()
        spacer_left.setFixedWidth(4)
        tb.addWidget(spacer_left)

        act_load_sample = QAction("导入示例数据", self)
        act_load_sample.setObjectName("toolbarAction")
        act_load_sample.triggered.connect(self._load_sample)
        tb.addAction(act_load_sample)

        act_load_file = QAction("加载运输记录", self)
        act_load_file.setObjectName("toolbarAction")
        act_load_file.triggered.connect(self._load_from_file)
        tb.addAction(act_load_file)

        act_save = QAction("保存当前记录", self)
        act_save.setObjectName("toolbarAction")
        act_save.triggered.connect(self._save_record)
        tb.addAction(act_save)

        tb.addSeparator()

        act_clear = QAction("清空复盘", self)
        act_clear.setObjectName("toolbarAction")
        act_clear.triggered.connect(self._clear_record)
        tb.addAction(act_clear)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        tb.addWidget(spacer)

        self.lbl_user_role = QLabel("  当前角色：冷链质控主管  ")
        self.lbl_user_role.setObjectName("roleLabel")
        tb.addWidget(self.lbl_user_role)

        self.lbl_datetime = QLabel()
        self.lbl_datetime.setObjectName("dateLabel")
        tb.addWidget(self.lbl_datetime)
        self._update_clock()
        self._clock_timer = self.startTimer(30000)

    def _build_central(self):
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._build_header_banner(layout)

        self.tabs = QTabWidget()
        self.tabs.setObjectName("mainTabs")
        self.tabs.setDocumentMode(True)

        self.tab_timeline = TimelineWindow()
        self.tab_impact = ImpactWindow()
        self.tab_export = ExportWindow()

        self.tab_impact.assessment_changed.connect(self._on_assessment_changed)

        self.tabs.addTab(self.tab_timeline, "  ① 告警时间轴  ")
        self.tabs.addTab(self.tab_impact, "  ② 温区影响估算  ")
        self.tabs.addTab(self.tab_export, "  ③ 证据包导出  ")

        layout.addWidget(self.tabs, 1)
        self.setCentralWidget(central)

    def _build_header_banner(self, parent_layout: QVBoxLayout):
        banner = QFrame()
        banner.setObjectName("appBanner")
        b_layout = QHBoxLayout(banner)
        b_layout.setContentsMargins(22, 14, 22, 14)
        b_layout.setSpacing(18)

        logo = QLabel("❄")
        logo.setObjectName("appLogo")
        logo.setAlignment(Qt.AlignCenter)

        title_wrap = QVBoxLayout()
        title_wrap.setSpacing(2)
        title = QLabel("冷藏车断电复盘工具")
        title.setObjectName("appTitle")
        subtitle = QLabel(
            "Cold Chain Power-Off Review　·　面向冷链质控 / 货主客服 / 保险理赔的专业复盘系统　·　非实时监控"
        )
        subtitle.setObjectName("appSubtitle")
        title_wrap.addWidget(title)
        title_wrap.addWidget(subtitle)

        self.btn_hint = QPushButton("使用指南")
        self.btn_hint.setObjectName("ghostButton")
        self.btn_hint.setCursor(Qt.PointingHandCursor)
        self.btn_hint.clicked.connect(self._show_guide)

        b_layout.addWidget(logo, 0, Qt.AlignVCenter)
        b_layout.addLayout(title_wrap, 1)
        b_layout.addWidget(self.btn_hint, 0, Qt.AlignVCenter)

        parent_layout.addWidget(banner)

    def _build_statusbar(self):
        sb = QStatusBar()
        sb.setObjectName("mainStatusBar")
        self.setStatusBar(sb)
        self.lbl_status = QLabel("就绪 · 请导入运输记录开始复盘")
        self.lbl_status.setObjectName("statusText")
        sb.addWidget(self.lbl_status, 1)
        self.lbl_record_hint = QLabel("记录：—")
        self.lbl_record_hint.setObjectName("statusHint")
        sb.addPermanentWidget(self.lbl_record_hint)

    def _apply_initial_hint(self):
        pass

    def _update_clock(self):
        now = datetime.now()
        self.lbl_datetime.setText(f"  {now.strftime('%Y-%m-%d  %H:%M')}  ")

    def timerEvent(self, event):
        if event.timerId() == self._clock_timer:
            self._update_clock()
        super().timerEvent(event)

    def _on_assessment_changed(self, assessment):
        self.tab_export.set_assessment(assessment)

    def _load_sample(self):
        try:
            record = generate_sample_record()
            self._set_record(record)
            self.lbl_status.setText("已加载示例运输记录 · 昨夜典型断电场景")
            self._auto_jump_after_load()
        except Exception as e:
            QMessageBox.critical(self, "加载失败", f"生成示例数据失败：\n{e}")

    def _auto_jump_after_load(self):
        self.tab_impact.set_record(self._record)
        self.tab_export.set_record(self._record)
        if self._record and self._record.cargo:
            self.tab_impact._load_from_record()
            self.tab_impact._do_assessment()
        self.tab_export._auto_fill_title()
        self.tab_export._refresh_photo_list()

    def _set_record(self, record: TransportRecord):
        self._record = record
        self.tab_timeline.set_record(record)
        self.tab_impact.set_record(record)
        self.tab_export.set_record(record)
        self.lbl_record_hint.setText(
            f"记录：{record.record_id}  |  {record.vehicle_plate}  |  {record.driver_name}"
        )

    def _load_from_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "加载运输记录", "",
            "运输记录文件 (*.pkl *.pickle *.json);;所有文件 (*.*)"
        )
        if not path:
            return
        try:
            if path.lower().endswith(".json"):
                with open(path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                record = self._dict_to_record(raw)
            else:
                with open(path, "rb") as f:
                    record = pickle.load(f)
            if not isinstance(record, TransportRecord):
                raise ValueError("文件内容不是有效的 TransportRecord 对象")
            self._set_record(record)
            self.lbl_status.setText(f"已加载运输记录：{record.record_id}")
            self._auto_jump_after_load()
        except Exception as e:
            QMessageBox.critical(self, "加载失败", f"无法解析文件：\n{e}")

    def _dict_to_record(self, d: dict) -> TransportRecord:
        from .models import (
            AlertEvent, TemperatureReading, CargoConfig,
            AlertType, AlertSeverity, CargoType
        )
        def parse_dt(s):
            if not s:
                return None
            try:
                return datetime.strptime(s, "%Y-%m-%dT%H:%M:%S")
            except Exception:
                return datetime.fromisoformat(s)

        cargo = None
        if d.get("cargo"):
            c = d["cargo"]
            cargo = CargoConfig(
                cargo_type=CargoType[c["cargo_type"]],
                cargo_name=c.get("cargo_name", ""),
                temp_min=float(c["temp_min"]),
                temp_max=float(c["temp_max"]),
                tolerance_minutes=int(c["tolerance_minutes"]),
                shipment_weight=float(c.get("shipment_weight", 0)),
                shipment_value=float(c.get("shipment_value", 0)),
            )
        alerts = []
        for a in d.get("alerts", []):
            alerts.append(AlertEvent(
                timestamp=parse_dt(a["timestamp"]),
                alert_type=AlertType[a["alert_type"]],
                severity=AlertSeverity[a["severity"]],
                description=a.get("description", ""),
                temperature=float(a["temperature"]) if a.get("temperature") is not None else None,
                operator=a.get("operator"),
                location=a.get("location"),
            ))
        tlog = []
        for t in d.get("temperature_log", []):
            tlog.append(TemperatureReading(
                timestamp=parse_dt(t["timestamp"]),
                temperature=float(t["temperature"]),
                zone=t.get("zone", "default"),
            ))
        return TransportRecord(
            record_id=d["record_id"],
            vehicle_plate=d["vehicle_plate"],
            driver_name=d["driver_name"],
            route_from=d["route_from"],
            route_to=d["route_to"],
            departure_time=parse_dt(d["departure_time"]),
            arrival_time=parse_dt(d.get("arrival_time")),
            loading_time=parse_dt(d.get("loading_time")),
            unloading_time=parse_dt(d.get("unloading_time")),
            cargo=cargo,
            alerts=alerts,
            temperature_log=tlog,
            track_images=d.get("track_images", []),
            driver_notes=d.get("driver_notes", ""),
            photo_paths=d.get("photo_paths", []),
        )

    def _save_record(self):
        if not self._record:
            QMessageBox.information(self, "提示", "当前没有可保存的运输记录。")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "保存运输记录",
            f"{self._record.record_id}.json",
            "JSON 记录文件 (*.json);;Pickle 记录文件 (*.pkl)"
        )
        if not path:
            return
        try:
            if path.lower().endswith(".json"):
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(self._record_to_dict(self._record), f, ensure_ascii=False, indent=2)
            else:
                with open(path, "wb") as f:
                    pickle.dump(self._record, f)
            self.lbl_status.setText(f"已保存至：{path}")
        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"保存出错：\n{e}")

    def _record_to_dict(self, r: TransportRecord) -> dict:
        def fmt(dt):
            return dt.strftime("%Y-%m-%dT%H:%M:%S") if dt else None
        return {
            "record_id": r.record_id,
            "vehicle_plate": r.vehicle_plate,
            "driver_name": r.driver_name,
            "route_from": r.route_from,
            "route_to": r.route_to,
            "departure_time": fmt(r.departure_time),
            "arrival_time": fmt(r.arrival_time),
            "loading_time": fmt(r.loading_time),
            "unloading_time": fmt(r.unloading_time),
            "cargo": {
                "cargo_type": r.cargo.cargo_type.name if r.cargo else None,
                "cargo_name": r.cargo.cargo_name if r.cargo else None,
                "temp_min": r.cargo.temp_min if r.cargo else None,
                "temp_max": r.cargo.temp_max if r.cargo else None,
                "tolerance_minutes": r.cargo.tolerance_minutes if r.cargo else None,
                "shipment_weight": r.cargo.shipment_weight if r.cargo else 0,
                "shipment_value": r.cargo.shipment_value if r.cargo else 0,
            } if r.cargo else None,
            "alerts": [
                {
                    "timestamp": fmt(a.timestamp),
                    "alert_type": a.alert_type.name,
                    "severity": a.severity.name,
                    "description": a.description,
                    "temperature": a.temperature,
                    "operator": a.operator,
                    "location": a.location,
                }
                for a in r.alerts
            ],
            "temperature_log": [
                {
                    "timestamp": fmt(t.timestamp),
                    "temperature": t.temperature,
                    "zone": t.zone,
                }
                for t in r.temperature_log
            ],
            "track_images": r.track_images,
            "driver_notes": r.driver_notes,
            "photo_paths": r.photo_paths,
        }

    def _clear_record(self):
        if not self._record:
            return
        ret = QMessageBox.question(
            self, "确认清空", "确定清空当前复盘数据吗？此操作不可撤销。",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if ret != QMessageBox.Yes:
            return
        self._record = None
        self.tab_timeline.set_record(
            TransportRecord(
                "TMP", "", "", "", "", datetime.now()
            )
        )
        self.tab_timeline._record = None
        self.tab_timeline._render_timeline()
        self.tab_timeline._render_summary()
        self.tab_timeline.chart.set_record(None)
        self.tab_impact.set_record(None)
        self.tab_export.set_record(None)
        self.tab_export.set_assessment(None)
        self.lbl_record_hint.setText("记录：—")
        self.lbl_status.setText("已清空 · 请重新导入运输记录")

    def _show_guide(self):
        text = (
            "本工具面向冷链质控主管、货主客服、保险理赔人员，用于「白天复盘昨夜异常」。\n\n"
            "标准使用流程：\n\n"
            "    1. 加载数据\n"
            "       • 点击顶部「导入示例数据」快速查看演示场景；\n"
            "       • 或点击「加载运输记录」读取车队导出的 JSON / PKL 文件。\n\n"
            "    2. 告警时间轴（①）\n"
            "       • 左侧按分钟逐一展示外接电断开、冷机停转、温度越线、司机确认、恢复供电等节点；\n"
            "       • 右侧温度曲线显示温区带（蓝色虚线区间），红色散点表示越线分钟，红竖线标注严重告警。\n\n"
            "    3. 温区影响估算（②）\n"
            "       • 填写货品类型（自动匹配冷冻/冷藏/医药/生鲜预设）、允许温度范围、装卸节点；\n"
            "       • 点击「从运输记录读取」可自动填充，再点「执行影响评估」；\n"
            "       • 结论会给出明确文字：「可能影响收货验收」或「未超过约定容忍时长」。\n\n"
            "    4. 证据包导出（③）\n"
            "       • 选择发送对象（货主/保险/承运商）；\n"
            "       • 勾选需要包含的内容（时间轴、评估结论、告警CSV、司机说明、照片、温度日志）；\n"
            "       • 「刷新预览」查看排版，「导出证据包」保存为 Markdown + CSV + TXT，可直接邮件发送。\n\n"
            "产品调性说明：\n"
            "    本工具不进行实时监控，重点在「减少扯皮」——所有数据按时间线对齐，责任链清晰可见，\n"
            "    证据包标准化输出，避免质控、货主、理赔三方各自表述。"
        )
        QMessageBox.information(self, "使用指南", text)
