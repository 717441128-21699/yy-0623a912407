from datetime import datetime, timedelta
from typing import Optional, List, Tuple, NamedTuple


class ExceedSegment(NamedTuple):
    start: datetime
    end: datetime
    minutes: int
    peak_temp: float

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QComboBox,
    QDoubleSpinBox, QSpinBox, QPushButton, QDateTimeEdit, QFormLayout,
    QTextEdit, QSizePolicy, QGroupBox, QLineEdit, QMessageBox, QInputDialog
)

from .models import (
    TransportRecord, CargoConfig, CargoType, TemperatureReading, ImpactAssessment, TempScheme
)


CARGO_PRESETS = {
    CargoType.FROZEN: {
        "temp_min": -25.0,
        "temp_max": -18.0,
        "tolerance": 45,
    },
    CargoType.CHILLED: {
        "temp_min": 0.0,
        "temp_max": 8.0,
        "tolerance": 90,
    },
    CargoType.MEDICAL: {
        "temp_min": 2.0,
        "temp_max": 8.0,
        "tolerance": 15,
    },
    CargoType.FRESH: {
        "temp_min": 4.0,
        "temp_max": 12.0,
        "tolerance": 120,
    },
    CargoType.SPECIAL: {
        "temp_min": -18.0,
        "temp_max": -18.0,
        "tolerance": 30,
    },
}


class ImpactWindow(QWidget):
    assessment_changed = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._record: Optional[TransportRecord] = None
        self._current_assessment: Optional[ImpactAssessment] = None
        self._scheme_baseline: Optional[dict] = None
        self._dirty = False
        self._suppress_dirty = False
        self._build_ui()
        self._connect_dirty_signals()

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(14)

        root.addWidget(self._build_input_panel(), 5)
        root.addWidget(self._build_result_panel(), 7)

    def _build_input_panel(self) -> QWidget:
        container = QFrame()
        container.setProperty("role", "panel")
        outer = QVBoxLayout(container)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        title = QLabel("  货品温区配置")
        title.setObjectName("panelTitle")
        title.setFixedHeight(40)
        outer.addWidget(title)

        scroll_content = QWidget()
        form_wrap = QVBoxLayout(scroll_content)
        form_wrap.setContentsMargins(16, 16, 16, 16)
        form_wrap.setSpacing(14)

        group_scheme = QGroupBox("评估方案（可新增/保存多套口径）")
        group_scheme.setObjectName("formGroup")
        form_scheme = QFormLayout(group_scheme)
        form_scheme.setSpacing(8)
        form_scheme.setContentsMargins(14, 18, 14, 14)

        self.cmb_scheme = QComboBox()
        self.cmb_scheme.setObjectName("schemeCombo")
        self.cmb_scheme.setMinimumHeight(30)
        self.cmb_scheme.addItem("自定义（手动填写参数）", None)
        self.cmb_scheme.currentIndexChanged.connect(self._apply_scheme)

        btn_scheme_row = QHBoxLayout()
        btn_scheme_row.setSpacing(6)
        self.btn_scheme_save_new = QPushButton("另存为新方案")
        self.btn_scheme_save_new.setObjectName("secondaryButton")
        self.btn_scheme_save_new.setCursor(Qt.PointingHandCursor)
        self.btn_scheme_save_new.setMinimumHeight(26)
        self.btn_scheme_save_new.clicked.connect(self._save_as_new_scheme)

        self.btn_scheme_update = QPushButton("更新当前方案")
        self.btn_scheme_update.setObjectName("secondaryButton")
        self.btn_scheme_update.setCursor(Qt.PointingHandCursor)
        self.btn_scheme_update.setMinimumHeight(26)
        self.btn_scheme_update.clicked.connect(self._update_current_scheme)

        self.btn_scheme_delete = QPushButton("删除方案")
        self.btn_scheme_delete.setObjectName("secondaryButton")
        self.btn_scheme_delete.setCursor(Qt.PointingHandCursor)
        self.btn_scheme_delete.setMinimumHeight(26)
        self.btn_scheme_delete.clicked.connect(self._delete_current_scheme)

        btn_scheme_row.addWidget(self.btn_scheme_save_new)
        btn_scheme_row.addWidget(self.btn_scheme_update)
        btn_scheme_row.addWidget(self.btn_scheme_delete)

        self.cmb_scheme_type = QComboBox()
        self.cmb_scheme_type.addItem("货主合同", "货主合同")
        self.cmb_scheme_type.addItem("保险条款", "保险条款")
        self.cmb_scheme_type.addItem("内部质控", "内部质控")
        self.cmb_scheme_type.addItem("自定义", "自定义")

        self.edt_scheme_desc = QLineEdit()
        self.edt_scheme_desc.setPlaceholderText("条款说明，如：收货合同第3.2条…")

        self.lbl_scheme_desc = QLabel("可选择货主合同/保险条款/内部质控等预设方案，或手动自定义参数")
        self.lbl_scheme_desc.setObjectName("schemeHint")
        self.lbl_scheme_desc.setWordWrap(True)
        self.lbl_scheme_desc.setStyleSheet("color: #546E7A; font-size: 11px;")

        self.lbl_dirty_hint = QLabel("")
        self.lbl_dirty_hint.setObjectName("dirtyHint")
        self.lbl_dirty_hint.setWordWrap(True)
        self.lbl_dirty_hint.setStyleSheet("color: #E65100; font-size: 11px; font-weight: 600;")
        self.lbl_dirty_hint.setVisible(False)

        scheme_row = QHBoxLayout()
        scheme_row.setSpacing(8)
        scheme_row.addWidget(self.cmb_scheme, 1)

        form_scheme.addRow("选择方案：", scheme_row)
        form_scheme.addRow("", btn_scheme_row)
        form_scheme.addRow("方案类型：", self.cmb_scheme_type)
        form_scheme.addRow("条款说明：", self.edt_scheme_desc)
        form_scheme.addRow("", self.lbl_dirty_hint)
        form_scheme.addRow("", self.lbl_scheme_desc)

        form_wrap.addWidget(group_scheme)

        group_cargo = QGroupBox("货品信息")
        group_cargo.setObjectName("formGroup")
        form_cargo = QFormLayout(group_cargo)
        form_cargo.setSpacing(10)
        form_cargo.setContentsMargins(14, 18, 14, 14)

        self.cmb_cargo_type = QComboBox()
        for t in CargoType:
            self.cmb_cargo_type.addItem(t.value, t)
        self.cmb_cargo_type.currentIndexChanged.connect(self._apply_cargo_preset)

        self.edt_cargo_name = QLineEdit()
        self.edt_cargo_name.setPlaceholderText("如：进口阿根廷去骨牛腩")

        form_cargo.addRow("货品类型：", self.cmb_cargo_type)
        form_cargo.addRow("货品名称：", self.edt_cargo_name)

        group_temp = QGroupBox("温度参数（单位：℃）")
        group_temp.setObjectName("formGroup")
        form_temp = QFormLayout(group_temp)
        form_temp.setSpacing(10)
        form_temp.setContentsMargins(14, 18, 14, 14)

        self.spn_temp_max = QDoubleSpinBox()
        self.spn_temp_max.setRange(-60, 40)
        self.spn_temp_max.setDecimals(1)
        self.spn_temp_max.setSingleStep(0.5)

        self.spn_temp_min = QDoubleSpinBox()
        self.spn_temp_min.setRange(-60, 40)
        self.spn_temp_min.setDecimals(1)
        self.spn_temp_min.setSingleStep(0.5)

        self.spn_tolerance = QSpinBox()
        self.spn_tolerance.setRange(0, 1440)
        self.spn_tolerance.setSuffix(" 分钟")

        form_temp.addRow("温度下限：", self.spn_temp_min)
        form_temp.addRow("温度上限：", self.spn_temp_max)
        form_temp.addRow("允许越线时长：", self.spn_tolerance)

        group_nodes = QGroupBox("装卸节点（分钟级）")
        group_nodes.setObjectName("formGroup")
        form_nodes = QFormLayout(group_nodes)
        form_nodes.setSpacing(10)
        form_nodes.setContentsMargins(14, 18, 14, 14)

        self.dt_loading = QDateTimeEdit()
        self.dt_loading.setDisplayFormat("MM-dd HH:mm")
        self.dt_loading.setCalendarPopup(True)

        self.dt_unloading = QDateTimeEdit()
        self.dt_unloading.setDisplayFormat("MM-dd HH:mm")
        self.dt_unloading.setCalendarPopup(True)

        form_nodes.addRow("装货完成：", self.dt_loading)
        form_nodes.addRow("到达卸货地：", self.dt_unloading)

        btn_calc = QPushButton("执行影响评估")
        btn_calc.setObjectName("primaryButton")
        btn_calc.setCursor(Qt.PointingHandCursor)
        btn_calc.setMinimumHeight(38)
        btn_calc.clicked.connect(self._do_assessment)

        btn_load_from_record = QPushButton("从运输记录读取")
        btn_load_from_record.setObjectName("secondaryButton")
        btn_load_from_record.setCursor(Qt.PointingHandCursor)
        btn_load_from_record.setMinimumHeight(34)
        btn_load_from_record.clicked.connect(self._load_from_record)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addWidget(btn_load_from_record)
        btn_row.addWidget(btn_calc, 1)

        form_wrap.addWidget(group_cargo)
        form_wrap.addWidget(group_temp)
        form_wrap.addWidget(group_nodes)
        form_wrap.addLayout(btn_row)
        form_wrap.addStretch(1)

        outer.addWidget(scroll_content, 1)
        return container

    def _build_result_panel(self) -> QWidget:
        container = QFrame()
        container.setProperty("role", "panel")
        outer = QVBoxLayout(container)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        title = QLabel("  温区影响评估结论")
        title.setObjectName("panelTitle")
        title.setFixedHeight(40)
        outer.addWidget(title)

        body = QVBoxLayout()
        body.setContentsMargins(16, 16, 16, 16)
        body.setSpacing(14)

        self.conclusion_banner = QFrame()
        self.conclusion_banner.setObjectName("conclusionBanner")
        banner_layout = QVBoxLayout(self.conclusion_banner)
        banner_layout.setContentsMargins(20, 18, 20, 18)
        banner_layout.setSpacing(6)

        self.lbl_conclusion_title = QLabel("请先填写货品参数并执行评估")
        self.lbl_conclusion_title.setObjectName("conclusionTitle")
        self.lbl_conclusion_detail = QLabel("使用左侧表单填写货品类型、允许温度范围、装卸节点，点击「执行影响评估」查看结论。")
        self.lbl_conclusion_detail.setObjectName("conclusionDetail")
        self.lbl_conclusion_detail.setWordWrap(True)

        banner_layout.addWidget(self.lbl_conclusion_title)
        banner_layout.addWidget(self.lbl_conclusion_detail)
        body.addWidget(self.conclusion_banner)

        stats_row = QHBoxLayout()
        stats_row.setSpacing(10)
        self.card_duration = self._make_metric_card("实际越线时长", "—", "分钟")
        self.card_tolerance = self._make_metric_card("约定容忍时长", "—", "分钟")
        self.card_peak = self._make_metric_card("温度峰值偏差", "—", "℃")
        stats_row.addWidget(self.card_duration["card"], 1)
        stats_row.addWidget(self.card_tolerance["card"], 1)
        stats_row.addWidget(self.card_peak["card"], 1)
        body.addLayout(stats_row)

        compare_group = QGroupBox("多方案对比（货主合同 / 保险条款 / 内部质控）")
        compare_group.setObjectName("formGroup")
        cp_layout = QVBoxLayout(compare_group)
        cp_layout.setContentsMargins(14, 18, 14, 14)
        cp_layout.setSpacing(8)

        self.txt_compare = QTextEdit()
        self.txt_compare.setReadOnly(True)
        self.txt_compare.setObjectName("compareTable")
        self.txt_compare.setMinimumHeight(150)
        self.txt_compare.setPlaceholderText(
            "执行评估后，此处将展示三套业务口径的对比：\n"
            "• 货主合同：最严谨，直接决定收货是否拒收\n"
            "• 保险条款：决定是否立案赔付以及赔付比例\n"
            "• 内部质控：车队内部考核与处罚依据\n"
            "每行显示：温区范围 / 容忍时长 / 越线分钟 / 结论 / 风险等级"
        )
        cp_layout.addWidget(self.txt_compare)

        body.addWidget(compare_group)

        detail_group = QGroupBox("责任链分析与建议")
        detail_group.setObjectName("formGroup")
        d_layout = QVBoxLayout(detail_group)
        d_layout.setContentsMargins(14, 18, 14, 14)
        d_layout.setSpacing(8)

        self.txt_detail = QTextEdit()
        self.txt_detail.setReadOnly(True)
        self.txt_detail.setObjectName("detailText")
        self.txt_detail.setPlaceholderText(
            "评估完成后，此处将显示完整的分析内容，包括：\n"
            "• 温度异常开始与恢复的精确时间\n"
            "• 超出约定容忍时长的具体分钟数\n"
            "• 对收货验收、货品品质的影响判断\n"
            "• 责任归属建议（设备故障/司机处置/不可抗力）\n"
            "• 是否建议触发保险理赔流程"
        )
        d_layout.addWidget(self.txt_detail)

        body.addWidget(detail_group, 1)

        outer.addLayout(body, 1)
        return container

    def _make_metric_card(self, label: str, value: str, unit: str) -> dict:
        card = QFrame()
        card.setObjectName("metricCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)
        lbl_label = QLabel(label)
        lbl_label.setObjectName("metricLabel")
        row = QHBoxLayout()
        row.setSpacing(4)
        lbl_value = QLabel(value)
        lbl_value.setObjectName("metricValue")
        lbl_unit = QLabel(unit)
        lbl_unit.setObjectName("metricUnit")
        row.addWidget(lbl_value)
        row.addWidget(lbl_unit)
        row.addStretch(1)
        layout.addWidget(lbl_label)
        layout.addLayout(row)
        return {
            "card": card,
            "value": lbl_value,
            "unit": lbl_unit,
        }

    def _load_from_record(self):
        if not self._record:
            QMessageBox.information(self, "提示", "请先导入运输记录。")
            return
        r = self._record
        self._suppress_dirty = True
        try:
            if r.temp_schemes:
                self._populate_schemes(select_name=r.temp_schemes[0].name)
                first_scheme: Optional[TempScheme] = self.cmb_scheme.currentData()
                if first_scheme and first_scheme.cargo:
                    c = first_scheme.cargo
                    ti = self.cmb_cargo_type.findData(c.cargo_type)
                    if ti >= 0:
                        self.cmb_cargo_type.setCurrentIndex(ti)
                    self.edt_cargo_name.setText(c.cargo_name)
                    self.spn_temp_min.setValue(c.temp_min)
                    self.spn_temp_max.setValue(c.temp_max)
                    self.spn_tolerance.setValue(c.tolerance_minutes)
                    t_idx = self.cmb_scheme_type.findData(first_scheme.scheme_type)
                    if t_idx >= 0:
                        self.cmb_scheme_type.setCurrentIndex(t_idx)
                    self.edt_scheme_desc.setText(first_scheme.description)
            elif r.cargo:
                self._populate_schemes()
                idx = self.cmb_cargo_type.findData(r.cargo.cargo_type)
                if idx >= 0:
                    self.cmb_cargo_type.setCurrentIndex(idx)
                self.edt_cargo_name.setText(r.cargo.cargo_name)
                self.spn_temp_min.setValue(r.cargo.temp_min)
                self.spn_temp_max.setValue(r.cargo.temp_max)
                self.spn_tolerance.setValue(r.cargo.tolerance_minutes)
            if r.loading_time:
                self.dt_loading.setDateTime(r.loading_time)
            if r.unloading_time:
                self.dt_unloading.setDateTime(r.unloading_time)
            self._capture_baseline()
        finally:
            self._suppress_dirty = False
        self._update_dirty_hint()

    def _apply_cargo_preset(self, idx: int):
        ctype: CargoType = self.cmb_cargo_type.itemData(idx)
        preset = CARGO_PRESETS.get(ctype)
        if preset:
            self.spn_temp_min.setValue(preset["temp_min"])
            self.spn_temp_max.setValue(preset["temp_max"])
            self.spn_tolerance.setValue(preset["tolerance"])

    def _connect_dirty_signals(self):
        self.cmb_cargo_type.currentIndexChanged.connect(lambda _=0: self._check_dirty())
        self.edt_cargo_name.textChanged.connect(lambda _=0: self._check_dirty())
        self.spn_temp_min.valueChanged.connect(lambda _=0: self._check_dirty())
        self.spn_temp_max.valueChanged.connect(lambda _=0: self._check_dirty())
        self.spn_tolerance.valueChanged.connect(lambda _=0: self._check_dirty())
        self.dt_loading.dateTimeChanged.connect(lambda _=0: self._check_dirty())
        self.dt_unloading.dateTimeChanged.connect(lambda _=0: self._check_dirty())
        self.cmb_scheme_type.currentIndexChanged.connect(lambda _=0: self._check_dirty())
        self.edt_scheme_desc.textChanged.connect(lambda _=0: self._check_dirty())

    def _capture_baseline(self):
        self._suppress_dirty = True
        try:
            self._scheme_baseline = {
                "cargo_type": self.cmb_cargo_type.currentData(),
                "cargo_name": self.edt_cargo_name.text().strip(),
                "temp_min": self.spn_temp_min.value(),
                "temp_max": self.spn_temp_max.value(),
                "tolerance": self.spn_tolerance.value(),
                "loading": self.dt_loading.dateTime().toPyDateTime(),
                "unloading": self.dt_unloading.dateTime().toPyDateTime(),
                "scheme_type": self.cmb_scheme_type.currentData(),
                "scheme_desc": self.edt_scheme_desc.text().strip(),
            }
            self._dirty = False
        finally:
            self._suppress_dirty = False
        self._update_dirty_hint()

    def _check_dirty(self):
        if self._suppress_dirty or self._scheme_baseline is None:
            return
        cur = {
            "cargo_type": self.cmb_cargo_type.currentData(),
            "cargo_name": self.edt_cargo_name.text().strip(),
            "temp_min": self.spn_temp_min.value(),
            "temp_max": self.spn_temp_max.value(),
            "tolerance": self.spn_tolerance.value(),
            "loading": self.dt_loading.dateTime().toPyDateTime(),
            "unloading": self.dt_unloading.dateTime().toPyDateTime(),
            "scheme_type": self.cmb_scheme_type.currentData(),
            "scheme_desc": self.edt_scheme_desc.text().strip(),
        }
        self._dirty = (cur != self._scheme_baseline)
        self._update_dirty_hint()

    def _update_dirty_hint(self):
        cur_scheme: Optional[TempScheme] = self.cmb_scheme.currentData()
        if cur_scheme is None:
            if self._dirty:
                self.lbl_dirty_hint.setText("● 当前为【自定义口径】：参数已手动调整，未保存为方案")
                self.lbl_dirty_hint.setVisible(True)
            else:
                self.lbl_dirty_hint.setText("● 当前为【自定义口径】")
                self.lbl_dirty_hint.setVisible(True)
        else:
            if self._dirty:
                self.lbl_dirty_hint.setText(
                    f"⚠ 当前方案【{cur_scheme.name}】参数已被手动修改，显示为自定义结果。"
                    f"点击「更新当前方案」保存，或重新选择方案恢复原值。"
                )
                self.lbl_dirty_hint.setVisible(True)
            else:
                self.lbl_dirty_hint.setVisible(False)
        self.btn_scheme_update.setEnabled(cur_scheme is not None)
        self.btn_scheme_delete.setEnabled(cur_scheme is not None)

    def _populate_schemes(self, select_name: Optional[str] = None):
        self._suppress_dirty = True
        try:
            self.cmb_scheme.clear()
            self.cmb_scheme.addItem("自定义（手动填写参数）", None)
            target_idx = 0
            if self._record and self._record.temp_schemes:
                for i, s in enumerate(self._record.temp_schemes):
                    self.cmb_scheme.addItem(f"【{s.scheme_type}】{s.name}", s)
                    if select_name and s.name == select_name:
                        target_idx = i + 1
            self.cmb_scheme.setCurrentIndex(target_idx)
        finally:
            self._suppress_dirty = False
        self.lbl_scheme_desc.setText(
            "可选择货主合同/保险条款/内部质控等预设方案，或手动自定义参数"
            + (f"　共已配置 {self.cmb_scheme.count() - 1} 套业务方案" if (self._record and self._record.temp_schemes) else "")
        )

    def set_record(self, record: TransportRecord):
        self._record = record
        self._populate_schemes()
        self._capture_baseline()

    def _apply_scheme(self, idx: int):
        if self._suppress_dirty:
            return
        scheme: Optional[TempScheme] = self.cmb_scheme.itemData(idx)
        self._suppress_dirty = True
        try:
            if not scheme:
                self.lbl_scheme_desc.setText("已切换为【自定义】模式，可手动调整温区与容忍时长参数")
                self.cmb_scheme_type.setCurrentIndex(self.cmb_scheme_type.findData("自定义"))
                self.edt_scheme_desc.setText("")
                self._capture_baseline()
                self._update_dirty_hint()
                if self._record and self._record.temperature_log:
                    self._do_assessment(silent=True)
                return
            c = scheme.cargo
            ti = self.cmb_cargo_type.findData(c.cargo_type)
            if ti >= 0:
                self.cmb_cargo_type.setCurrentIndex(ti)
            self.edt_cargo_name.setText(c.cargo_name)
            self.spn_temp_min.setValue(c.temp_min)
            self.spn_temp_max.setValue(c.temp_max)
            self.spn_tolerance.setValue(c.tolerance_minutes)
            t_idx = self.cmb_scheme_type.findData(scheme.scheme_type)
            if t_idx >= 0:
                self.cmb_scheme_type.setCurrentIndex(t_idx)
            self.edt_scheme_desc.setText(scheme.description)
            desc = f"已加载【{scheme.scheme_type}】{scheme.name}"
            if scheme.description:
                desc += f"　｜　{scheme.description}"
            self.lbl_scheme_desc.setText(desc)
            self.lbl_scheme_desc.setToolTip(scheme.description or "")
            self._capture_baseline()
        finally:
            self._suppress_dirty = False
        self._update_dirty_hint()
        if self._record and self._record.temperature_log:
            self._do_assessment(silent=True)

    def _current_cargo_from_ui(self) -> CargoConfig:
        return CargoConfig(
            cargo_type=self.cmb_cargo_type.currentData(),
            cargo_name=self.edt_cargo_name.text().strip() or "未填写",
            temp_min=self.spn_temp_min.value(),
            temp_max=self.spn_temp_max.value(),
            tolerance_minutes=self.spn_tolerance.value(),
            shipment_weight=(self._record.cargo.shipment_weight if (self._record and self._record.cargo) else 0.0),
            shipment_value=(self._record.cargo.shipment_value if (self._record and self._record.cargo) else 0.0),
        )

    def _save_as_new_scheme(self):
        if not self._record:
            QMessageBox.information(self, "提示", "请先导入运输记录。")
            return
        name, ok = QInputDialog.getText(
            self, "另存为新方案",
            "请输入方案名称（如：货主合同2025版、保险理赔阈值V3等）：",
            text=f"新方案{len(self._record.temp_schemes) + 1}"
        )
        if not ok or not name.strip():
            return
        name = name.strip()
        for s in self._record.temp_schemes:
            if s.name == name:
                QMessageBox.warning(self, "名称冲突", f"已存在同名方案「{name}」，请换个名字或使用「更新当前方案」。")
                return
        scheme = TempScheme(
            name=name,
            scheme_type=self.cmb_scheme_type.currentData() or "自定义",
            description=self.edt_scheme_desc.text().strip(),
            cargo=self._current_cargo_from_ui(),
        )
        self._record.temp_schemes.append(scheme)
        self._populate_schemes(select_name=name)
        self._capture_baseline()
        self._update_dirty_hint()
        QMessageBox.information(self, "已保存", f"新方案「{name}」已保存到当前运输记录，保存记录文件后可永久保留。")

    def _update_current_scheme(self):
        cur: Optional[TempScheme] = self.cmb_scheme.currentData()
        if not cur:
            QMessageBox.information(self, "提示", "请先选择一个已保存的方案。")
            return
        cur.cargo = self._current_cargo_from_ui()
        cur.scheme_type = self.cmb_scheme_type.currentData() or "自定义"
        cur.description = self.edt_scheme_desc.text().strip()
        self._populate_schemes(select_name=cur.name)
        self._capture_baseline()
        self._update_dirty_hint()
        QMessageBox.information(self, "已更新", f"方案「{cur.name}」参数已更新。")

    def _delete_current_scheme(self):
        cur: Optional[TempScheme] = self.cmb_scheme.currentData()
        if not cur:
            QMessageBox.information(self, "提示", "请先选择一个已保存的方案。")
            return
        ret = QMessageBox.question(
            self, "确认删除",
            f"确定删除方案「{cur.name}」吗？删除后可通过重新加载记录恢复（未保存的话）。",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if ret != QMessageBox.Yes:
            return
        self._record.temp_schemes = [s for s in self._record.temp_schemes if s.name != cur.name]
        self._populate_schemes()
        self._capture_baseline()
        self._update_dirty_hint()

    def _evaluate_one_scheme(
        self, scheme_name: str, cargo: CargoConfig, analysis_start, analysis_end
    ) -> Optional[ImpactAssessment]:
        tmin = cargo.temp_min
        tmax = cargo.temp_max
        tolerance = cargo.tolerance_minutes
        if tmin >= tmax or analysis_start >= analysis_end:
            return None

        result = self._analyze_temperature(
            self._record.temperature_log, tmin, tmax, analysis_start, analysis_end
        )
        segments = result["segments"]
        exceed_duration = result["total_minutes"]
        exceed_start = result["first_exceed"]
        exceed_end = result["last_exceed"]
        peak_temp = result["peak_temp"]

        affected_parts = []
        if segments:
            for i, seg in enumerate(segments, 1):
                affected_parts.append(
                    f"第{i}段 {seg.start.strftime('%H:%M')}~{seg.end.strftime('%H:%M')} ({seg.minutes}分钟)"
                )
            affected_period = "；".join(affected_parts)
        elif exceed_start and exceed_end:
            affected_period = (
                f"{exceed_start.strftime('%m-%d %H:%M')} ~ "
                f"{exceed_end.strftime('%m-%d %H:%M')}"
            )
        else:
            affected_period = "无越线记录"

        is_acceptable = exceed_duration <= tolerance
        if is_acceptable and exceed_duration == 0:
            conclusion = "温区全程稳定"
            risk_level = "低"
        elif is_acceptable:
            conclusion = "未超过约定容忍时长"
            risk_level = "中低"
        else:
            conclusion = "可能影响收货验收"
            risk_level = "高"

        return ImpactAssessment(
            is_acceptable=is_acceptable,
            exceed_duration_minutes=exceed_duration,
            tolerance_minutes=tolerance,
            peak_temperature=peak_temp or 0.0,
            temp_min=tmin,
            temp_max=tmax,
            affected_period=affected_period,
            conclusion=conclusion,
            detail="",
            risk_level=risk_level,
            scheme_name=scheme_name,
        )

    def _do_assessment(self, silent: bool = False):
        if not self._record:
            if not silent:
                QMessageBox.warning(self, "缺少运输记录", "请先导入或加载运输记录数据。")
            return

        tmin = self.spn_temp_min.value()
        tmax = self.spn_temp_max.value()
        tolerance = self.spn_tolerance.value()
        analysis_start = self.dt_loading.dateTime().toPyDateTime()
        analysis_end = self.dt_unloading.dateTime().toPyDateTime()

        if tmin >= tmax:
            if not silent:
                QMessageBox.warning(self, "参数错误", "温度下限必须低于温度上限。")
            return
        if analysis_start >= analysis_end:
            if not silent:
                QMessageBox.warning(self, "参数错误", "装货完成时间必须早于到达卸货地时间。")
            return

        current_scheme: Optional[TempScheme] = self.cmb_scheme.currentData()
        scheme_name = current_scheme.name if current_scheme else "自定义"

        cargo = CargoConfig(
            cargo_type=self.cmb_cargo_type.currentData(),
            cargo_name=self.edt_cargo_name.text().strip() or "未填写",
            temp_min=tmin,
            temp_max=tmax,
            tolerance_minutes=tolerance,
        )
        self._record.cargo = cargo

        result = self._analyze_temperature(
            self._record.temperature_log, tmin, tmax, analysis_start, analysis_end
        )
        exceed_readings = result["exceeded"]
        segments = result["segments"]
        exceed_duration = result["total_minutes"]
        exceed_start = result["first_exceed"]
        exceed_end = result["last_exceed"]
        peak_temp = result["peak_temp"]

        affected_parts = []
        if segments:
            for i, seg in enumerate(segments, 1):
                affected_parts.append(
                    f"第{i}段 {seg.start.strftime('%H:%M')}~{seg.end.strftime('%H:%M')} ({seg.minutes}分钟)"
                )
            affected_period = "；".join(affected_parts)
        elif exceed_start and exceed_end:
            affected_period = (
                f"{exceed_start.strftime('%m-%d %H:%M')} ~ "
                f"{exceed_end.strftime('%m-%d %H:%M')}"
            )
        else:
            affected_period = "无越线记录"

        is_acceptable = exceed_duration <= tolerance
        peak_deviation = 0.0
        if peak_temp is not None:
            if peak_temp > tmax:
                peak_deviation = round(peak_temp - tmax, 1)
            elif peak_temp < tmin:
                peak_deviation = round(tmin - peak_temp, 1)

        if is_acceptable and exceed_duration == 0:
            conclusion = "温区全程稳定"
            risk_level = "低"
        elif is_acceptable:
            conclusion = "未超过约定容忍时长"
            risk_level = "中低"
        else:
            conclusion = "可能影响收货验收"
            risk_level = "高"

        detail = self._build_detail_text(
            is_acceptable, exceed_duration, tolerance, peak_temp, peak_deviation,
            exceed_start, exceed_end, affected_period, cargo, segments,
            analysis_start, analysis_end
        )

        assessment = ImpactAssessment(
            is_acceptable=is_acceptable,
            exceed_duration_minutes=exceed_duration,
            tolerance_minutes=tolerance,
            peak_temperature=peak_temp or 0.0,
            temp_min=tmin,
            temp_max=tmax,
            affected_period=affected_period,
            conclusion=conclusion,
            detail=detail,
            risk_level=risk_level,
            scheme_name=scheme_name,
        )
        self._current_assessment = assessment

        # 生成多方案对比
        comparisons = [assessment]
        if self._record.temp_schemes:
            for s in self._record.temp_schemes:
                if current_scheme and s.name == current_scheme.name:
                    continue  # 避免重复（当前方案已在首位）
                r = self._evaluate_one_scheme(s.name, s.cargo, analysis_start, analysis_end)
                if r:
                    comparisons.append(r)

        self._render_assessment(assessment)
        self._render_comparison(comparisons)
        self.assessment_changed.emit(assessment)

    def _render_comparison(self, comparisons: List[ImpactAssessment]):
        if not comparisons:
            self.txt_compare.setPlainText("（无可对比方案）")
            return
        lines = []
        lines.append("┌" + "─" * 16 + "┬" + "─" * 14 + "┬" + "─" * 10 + "┬" + "─" * 12 + "┬" + "─" * 18 + "┬" + "─" * 10 + "┐")
        lines.append("│" + "评估方案".center(16) + "│" + "温区(℃)".center(14) + "│" + "容忍".center(10) + "│" + "越线分钟".center(12) + "│" + "结论".center(18) + "│" + "风险等级".center(10) + "│")
        lines.append("├" + "─" * 16 + "┼" + "─" * 14 + "┼" + "─" * 10 + "┼" + "─" * 12 + "┼" + "─" * 18 + "┼" + "─" * 10 + "┤")
        for a in comparisons:
            name = (a.scheme_name or "自定义")[:15]
            temp_range = f"{a.temp_min:.0f}~{a.temp_max:.0f}"
            tol = f"{a.tolerance_minutes}分"
            exceed = f"{a.exceed_duration_minutes}分"
            if a.exceed_duration_minutes == 0:
                marker = "●"
                color_note = ""
            elif a.is_acceptable:
                marker = "▲"
                color_note = ""
            else:
                marker = "✗"
                color_note = ""
            concl = f"{marker}{a.conclusion[:8]}"
            risk = a.risk_level
            lines.append(
                "│" + name.center(16) + "│" + temp_range.center(14) + "│"
                + tol.center(10) + "│" + exceed.center(12) + "│"
                + concl.center(18) + "│" + risk.center(10) + "│"
            )
        lines.append("└" + "─" * 16 + "┴" + "─" * 14 + "┴" + "─" * 10 + "┴" + "─" * 12 + "┴" + "─" * 18 + "┴" + "─" * 10 + "┘")
        lines.append("")
        lines.append("符号说明：● 全程稳定  ▲ 短时越线但可接受  ✗ 超过容忍阈值")
        lines.append("")
        diff = []
        ok = [c for c in comparisons if c.is_acceptable]
        bad = [c for c in comparisons if not c.is_acceptable]
        if ok and bad:
            diff.append(
                f"⚠ 方案差异：{len(bad)} 套方案判定「可能影响收货验收」，"
                f"{len(ok)} 套方案判定「可接受」。"
            )
            if bad and ok:
                worst = max(bad, key=lambda c: c.exceed_duration_minutes)
                best = min(ok, key=lambda c: c.exceed_duration_minutes)
                diff.append(
                    f"  → 最严口径【{worst.scheme_name}】：超出容忍 {worst.exceed_duration_minutes - worst.tolerance_minutes} 分钟"
                )
                diff.append(
                    f"  → 最松口径【{best.scheme_name}】：尚余容忍 {best.tolerance_minutes - best.exceed_duration_minutes} 分钟"
                )
        elif len(comparisons) > 1 and all(c.is_acceptable for c in comparisons):
            diff.append("✓ 所有方案均判定可接受或温区稳定，但内部考核仍需参考严格口径。")
        elif len(comparisons) > 1 and not any(c.is_acceptable for c in comparisons):
            diff.append("✗ 所有口径均判定超过容忍时长，建议按最严重方案启动理赔流程。")
        lines.extend(diff)
        self.txt_compare.setPlainText("\n".join(lines))

    def _analyze_temperature(
        self, readings: List[TemperatureReading], tmin: float, tmax: float,
        start_dt: datetime, end_dt: datetime
    ) -> dict:
        if not readings:
            return {
                "exceeded": [],
                "segments": [],
                "total_minutes": 0,
                "first_exceed": None,
                "last_exceed": None,
                "peak_temp": None,
                "analysis_start": start_dt,
                "analysis_end": end_dt,
            }

        in_range = [
            r for r in readings
            if start_dt <= r.timestamp <= end_dt
        ]
        exceeded = [r for r in in_range if r.temperature < tmin or r.temperature > tmax]

        if not exceeded:
            return {
                "exceeded": [],
                "segments": [],
                "total_minutes": 0,
                "first_exceed": None,
                "last_exceed": None,
                "peak_temp": None,
                "analysis_start": start_dt,
                "analysis_end": end_dt,
            }

        segments: List[ExceedSegment] = []
        current_seg: List[TemperatureReading] = []

        sorted_readings = sorted(in_range, key=lambda r: r.timestamp)
        for r in sorted_readings:
            is_exceed = r.temperature < tmin or r.temperature > tmax
            if is_exceed:
                current_seg.append(r)
            else:
                if current_seg:
                    if len(current_seg) >= 1:
                        seg_start = current_seg[0].timestamp
                        seg_end = current_seg[-1].timestamp
                        minutes = max(1, int((seg_end - seg_start).total_seconds() / 60) + 1)
                        peak = max(current_seg, key=lambda x: abs(x.temperature - ((tmin + tmax) / 2))).temperature
                        segments.append(ExceedSegment(seg_start, seg_end, minutes, peak))
                    current_seg = []

        if current_seg:
            seg_start = current_seg[0].timestamp
            seg_end = current_seg[-1].timestamp
            minutes = max(1, int((seg_end - seg_start).total_seconds() / 60) + 1)
            peak = max(current_seg, key=lambda x: abs(x.temperature - ((tmin + tmax) / 2))).temperature
            segments.append(ExceedSegment(seg_start, seg_end, minutes, peak))

        total_minutes = sum(s.minutes for s in segments)
        peak = max(exceeded, key=lambda r: abs(r.temperature - ((tmin + tmax) / 2))).temperature

        return {
            "exceeded": exceeded,
            "segments": segments,
            "total_minutes": total_minutes,
            "first_exceed": exceeded[0].timestamp,
            "last_exceed": exceeded[-1].timestamp,
            "peak_temp": peak,
            "analysis_start": start_dt,
            "analysis_end": end_dt,
        }

    def _build_detail_text(
        self, is_acceptable, exceed_dur, tolerance, peak_temp, peak_dev,
        start, end, period, cargo, segments, analysis_start, analysis_end
    ) -> str:
        lines = []
        lines.append("═" * 38 + "  评估摘要  " + "═" * 38)
        lines.append(f"货品种类：{cargo.cargo_type.value}　　名称：{cargo.cargo_name}")
        lines.append(f"约定温区：{cargo.temp_min:.1f}℃ ~ {cargo.temp_max:.1f}℃　　容忍越线：{tolerance} 分钟")
        lines.append(
            f"评估区间：{analysis_start.strftime('%Y-%m-%d %H:%M')} ~ {analysis_end.strftime('%Y-%m-%d %H:%M')}"
            "（装货完成 → 到达卸货地）"
        )
        lines.append("")
        lines.append("─" * 88)
        lines.append("【一】温度异常时段")
        if segments:
            lines.append(f"  • 分段异常明细（共 {len(segments)} 段，仅累加越线分钟，不含中间正常时段）：")
            for i, seg in enumerate(segments, 1):
                lines.append(
                    f"     第{i}段：{seg.start.strftime('%Y-%m-%d %H:%M')} ~ "
                    f"{seg.end.strftime('%H:%M')}　持续 {seg.minutes} 分钟　峰值 {seg.peak_temp:.1f}℃"
                )
            lines.append(f"  • 越线累计时长：{exceed_dur} 分钟（{sum(s.minutes for s in segments)} 分钟 = {' + '.join(str(s.minutes) for s in segments)}）")
            lines.append(f"  • 首次越线时间：{start.strftime('%Y-%m-%d %H:%M')}")
            lines.append(f"  • 末次越线时间：{end.strftime('%Y-%m-%d %H:%M')}")
            if peak_temp is not None:
                lines.append(f"  • 全程温度峰值：{peak_temp:.1f}℃（偏离边界 {peak_dev:+.1f}℃）")
        elif start and end:
            lines.append(f"  • 首次越线时间：{start.strftime('%Y-%m-%d %H:%M')}")
            lines.append(f"  • 恢复至正常温区时间：{end.strftime('%Y-%m-%d %H:%M')}")
            lines.append(f"  • 越线累计时长：{exceed_dur} 分钟")
            if peak_temp is not None:
                lines.append(f"  • 温度峰值：{peak_temp:.1f}℃（偏离边界 {peak_dev:+.1f}℃）")
        else:
            lines.append("  • 评估区间内未检测到温度越线，运输过程温区稳定。")

        lines.append("")
        lines.append("【二】影响程度判断")
        if not start:
            lines.append("  • 本次运输温区控制完全符合约定，不影响收货验收。")
        elif is_acceptable:
            lines.append(
                f"  • 越线时长 {exceed_dur} 分钟，小于约定容忍时长 {tolerance} 分钟。"
            )
            lines.append(
                "  • 结论：未超过约定容忍时长。结合货品品类特性，"
                "该越线通常不影响货品品质与收货验收。"
            )
            if cargo.cargo_type == CargoType.FROZEN:
                lines.append("  • 说明：冷冻货品热容量大，短时温升不致形成解冻循环。")
            elif cargo.cargo_type == CargoType.MEDICAL:
                lines.append("  • 说明：医药冷链容忍窗口较短，建议后续加强冷机预检查。")
        else:
            over = exceed_dur - tolerance
            lines.append(
                f"  • 越线时长 {exceed_dur} 分钟，超过约定容忍时长 {tolerance} 分钟（超出 {over} 分钟）。"
            )
            lines.append("  • 结论：可能影响收货验收。")
            lines.append(
                "  • 建议：收货方在卸货前逐托盘抽检外观（是否有解冻、软化、凝露），"
                "并保留温度记录仪原始数据作为后续交涉依据。"
            )
            if peak_temp is not None and cargo.cargo_type == CargoType.FROZEN:
                if peak_temp > -10:
                    lines.append("  • 风险提示：峰值温度高于 -10℃，表层货品可能已部分解冻。")
            elif cargo.cargo_type == CargoType.MEDICAL:
                lines.append("  • 风险提示：医药冷链超出容忍窗口，建议直接启动偏差调查流程。")

        lines.append("")
        lines.append("【三】责任链还原建议")
        if self._record:
            driver_confirms = [
                a for a in self._record.alerts
                if a.alert_type.name == "DRIVER_CONFIRM"
            ]
            cooler_stop = [
                a for a in self._record.alerts
                if a.alert_type.name == "COOLER_STOP"
            ]
            restore = [
                a for a in self._record.alerts
                if a.alert_type.name in ("POWER_RESTORE", "COOLER_RESTART")
            ]
            if cooler_stop and driver_confirms:
                lag = (driver_confirms[0].timestamp - cooler_stop[0].timestamp).total_seconds() / 60
                lines.append(f"  • 冷机告警 → 司机首次确认：{lag:.0f} 分钟（行业建议 ≤ 10 分钟）")
                if lag <= 10:
                    lines.append("  • 司机响应及时，处置链路无明显延误。")
                else:
                    lines.append(f"  • 司机响应偏慢，存在 {lag - 10:.0f} 分钟的处置空窗。")
            if restore and cooler_stop:
                dt = (restore[0].timestamp - cooler_stop[0].timestamp).total_seconds() / 60
                lines.append(f"  • 冷机停机 → 恢复供电：{dt:.0f} 分钟（含维修支援时间）")
            lines.append("  • 以上节点均已在「告警时间轴」面板中标注，可作为责任划分客观依据。")

        lines.append("")
        lines.append("【四】理赔建议")
        if not start:
            lines.append("  • 无异常，无需理赔介入。")
        elif is_acceptable:
            lines.append("  • 未超出约定阈值，建议在运输服务考评中记录，不建议启动正式理赔。")
        else:
            lines.append("  • 超出约定容忍阈值，建议：")
            lines.append("    1) 收集温度日志、告警时间轴、司机说明、现场照片组成证据包；")
            lines.append("    2) 评估货品损失比例（抽检或全检）；")
            lines.append("    3) 对照运输合同条款启动保险理赔或承运商赔付流程。")

        lines.append("")
        lines.append("═" * 88)
        return "\n".join(lines)

    def _render_assessment(self, a: ImpactAssessment):
        self.card_duration["value"].setText(str(a.exceed_duration_minutes))
        self.card_tolerance["value"].setText(str(a.tolerance_minutes))
        if a.peak_temperature is not None and a.peak_temperature != 0.0:
            peak_dev = 0.0
            if a.peak_temperature > a.temp_max:
                peak_dev = a.peak_temperature - a.temp_max
            elif a.peak_temperature < a.temp_min:
                peak_dev = a.temp_min - a.peak_temperature
            self.card_peak["value"].setText(f"{peak_dev:+.1f}")
        else:
            self.card_peak["value"].setText("0.0")

        if a.is_acceptable:
            if a.exceed_duration_minutes == 0:
                self.conclusion_banner.setProperty("status", "ok")
                self.lbl_conclusion_title.setText("✓ 全程温区稳定，无越线记录")
                self.lbl_conclusion_title.setStyleSheet("color: #2E7D32; font-size: 18px; font-weight: 700;")
            else:
                self.conclusion_banner.setProperty("status", "warn")
                self.lbl_conclusion_title.setText(f"● {a.conclusion}（越线 {a.exceed_duration_minutes} 分钟）")
                self.lbl_conclusion_title.setStyleSheet("color: #F57C00; font-size: 18px; font-weight: 700;")
        else:
            self.conclusion_banner.setProperty("status", "bad")
            self.lbl_conclusion_title.setText(
                f"✗ {a.conclusion}（超出容忍 {a.exceed_duration_minutes - a.tolerance_minutes} 分钟）"
            )
            self.lbl_conclusion_title.setStyleSheet("color: #C62828; font-size: 18px; font-weight: 700;")

        self.lbl_conclusion_detail.setText(
            f"异常时段：{a.affected_period}　　风险等级：{a.risk_level}"
        )
        self.txt_detail.setPlainText(a.detail)
        self.conclusion_banner.style().unpolish(self.conclusion_banner)
        self.conclusion_banner.style().polish(self.conclusion_banner)

    def get_assessment(self) -> Optional[ImpactAssessment]:
        return self._current_assessment
