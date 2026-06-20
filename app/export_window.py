import os
import shutil
import zipfile
from datetime import datetime
from typing import Optional, List

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton,
    QComboBox, QLineEdit, QCheckBox, QListWidget, QListWidgetItem,
    QTextEdit, QFileDialog, QMessageBox, QGroupBox, QFormLayout,
    QSizePolicy, QProgressBar
)

from .models import TransportRecord, ImpactAssessment, EvidencePackage, AlertSeverity, ResponsibilityPhase, TempScheme, CargoConfig, CargoType


class ExportWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._record: Optional[TransportRecord] = None
        self._assessment: Optional[ImpactAssessment] = None
        self._build_ui()

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(14)

        root.addWidget(self._build_config_panel(), 5)
        root.addWidget(self._build_preview_panel(), 7)

    def _build_config_panel(self) -> QWidget:
        container = QFrame()
        container.setProperty("role", "panel")
        outer = QVBoxLayout(container)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        title = QLabel("  证据包配置")
        title.setObjectName("panelTitle")
        title.setFixedHeight(40)
        outer.addWidget(title)

        body = QVBoxLayout()
        body.setContentsMargins(16, 16, 16, 16)
        body.setSpacing(14)

        meta_group = QGroupBox("基础信息")
        meta_group.setObjectName("formGroup")
        mf = QFormLayout(meta_group)
        mf.setSpacing(10)
        mf.setContentsMargins(14, 18, 14, 14)

        self.cmb_recipient = QComboBox()
        self.cmb_recipient.addItem("货主客服 / 收货方采购", "owner")
        self.cmb_recipient.addItem("保险理赔专员", "insurance")
        self.cmb_recipient.addItem("承运商质控部门", "carrier")
        self.cmb_recipient.addItem("通用用途（所有信息）", "all")

        self.edt_package_title = QLineEdit()
        self.edt_package_title.setPlaceholderText("自动生成，可修改")

        mf.addRow("发送对象：", self.cmb_recipient)
        mf.addRow("证据包标题：", self.edt_package_title)

        body.addWidget(meta_group)

        content_group = QGroupBox("包含内容")
        content_group.setObjectName("formGroup")
        cf = QVBoxLayout(content_group)
        cf.setSpacing(6)
        cf.setContentsMargins(14, 18, 14, 14)

        self.chk_timeline = QCheckBox("告警时间轴汇总（关键节点、责任链时间差）")
        self.chk_timeline.setChecked(True)
        self.chk_impact = QCheckBox("温区影响评估结论（含风险等级、理赔建议）")
        self.chk_impact.setChecked(True)
        self.chk_alerts = QCheckBox("完整告警记录（逐条导出为表格文本）")
        self.chk_alerts.setChecked(True)
        self.chk_driver_statement = QCheckBox("司机书面处置说明")
        self.chk_driver_statement.setChecked(True)
        self.chk_temp_log = QCheckBox("温度日志明细（CSV 格式，便于二次分析）")
        self.chk_temp_log.setChecked(False)
        self.chk_photos = QCheckBox("现场照片与轨迹截图清单（附文件名索引）")
        self.chk_photos.setChecked(True)

        for chk in (
            self.chk_timeline, self.chk_impact, self.chk_alerts,
            self.chk_driver_statement, self.chk_temp_log, self.chk_photos,
        ):
            cf.addWidget(chk)

        body.addWidget(content_group)

        pack_group = QGroupBox("打包选项")
        pack_group.setObjectName("formGroup")
        pf = QVBoxLayout(pack_group)
        pf.setSpacing(6)
        pf.setContentsMargins(14, 18, 14, 14)

        self.chk_zip = QCheckBox("导出后自动打包为 ZIP 压缩包（文件名含运输编号 + 车牌）")
        self.chk_zip.setChecked(True)
        self.chk_zip.setToolTip("勾选后导出时会将 Markdown、CSV、司机说明和附件一起打成一个 ZIP 文件，方便邮件/微信发送")
        pf.addWidget(self.chk_zip)

        body.addWidget(pack_group)

        list_group = QGroupBox("现场照片 / 截图（可勾选）")
        list_group.setObjectName("formGroup")
        lf = QVBoxLayout(list_group)
        lf.setSpacing(6)
        lf.setContentsMargins(14, 18, 14, 14)

        self.list_photos = QListWidget()
        self.list_photos.setSelectionMode(QListWidget.NoSelection)
        self.list_photos.setObjectName("photoList")
        lf.addWidget(self.list_photos)

        body.addWidget(list_group, 1)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setTextVisible(True)
        self.progress.setRange(0, 100)
        body.addWidget(self.progress)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        self.btn_refresh = QPushButton("刷新预览")
        self.btn_refresh.setObjectName("secondaryButton")
        self.btn_refresh.setCursor(Qt.PointingHandCursor)
        self.btn_refresh.setMinimumHeight(36)
        self.btn_refresh.clicked.connect(self._build_preview)

        self.btn_export = QPushButton("导出证据包")
        self.btn_export.setObjectName("primaryButton")
        self.btn_export.setCursor(Qt.PointingHandCursor)
        self.btn_export.setMinimumHeight(36)
        self.btn_export.clicked.connect(self._export_package)

        btn_row.addWidget(self.btn_refresh, 1)
        btn_row.addWidget(self.btn_export, 2)
        body.addLayout(btn_row)

        outer.addLayout(body, 1)
        return container

    def _build_preview_panel(self) -> QWidget:
        container = QFrame()
        container.setProperty("role", "panel")
        outer = QVBoxLayout(container)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        title = QLabel("  证据包内容预览")
        title.setObjectName("panelTitle")
        title.setFixedHeight(40)
        outer.addWidget(title)

        body = QVBoxLayout()
        body.setContentsMargins(16, 16, 16, 16)
        body.setSpacing(12)

        header = QFrame()
        header.setObjectName("previewHeader")
        hl = QVBoxLayout(header)
        hl.setContentsMargins(14, 12, 14, 12)
        hl.setSpacing(4)
        self.lbl_preview_title = QLabel("等待配置...")
        self.lbl_preview_title.setObjectName("previewTitle")
        self.lbl_preview_meta = QLabel("完成运输记录导入 + 温区评估后，点击「刷新预览」查看")
        self.lbl_preview_meta.setObjectName("previewMeta")
        hl.addWidget(self.lbl_preview_title)
        hl.addWidget(self.lbl_preview_meta)

        body.addWidget(header)

        self.txt_preview = QTextEdit()
        self.txt_preview.setReadOnly(True)
        self.txt_preview.setObjectName("previewText")
        self.txt_preview.setPlaceholderText(
            "预览区将显示：\n"
            "  1. 证据包封面信息（编号、发送对象、生成时间）\n"
            "  2. 告警时间轴汇总\n"
            "  3. 温区影响评估结论\n"
            "  4. 完整告警记录\n"
            "  5. 司机处置说明\n"
            "  6. 附件清单（照片、截图、温度日志）\n"
        )
        body.addWidget(self.txt_preview, 1)

        outer.addLayout(body, 1)
        return container

    def set_record(self, record: TransportRecord):
        self._record = record
        self._refresh_photo_list()
        self._auto_fill_title()

    def set_assessment(self, assessment: Optional[ImpactAssessment]):
        self._assessment = assessment
        self._auto_fill_title()

    def _auto_fill_title(self):
        if not self._record:
            return
        r = self._record
        date_str = r.departure_time.strftime("%Y%m%d")
        title = f"冷藏车断电事件证据包_{r.record_id}_{date_str}_{r.vehicle_plate.replace('·', '')}"
        self.edt_package_title.setText(title)

    def _refresh_photo_list(self):
        self.list_photos.clear()
        if not self._record:
            return
        for idx, att in enumerate(self._record.attachments):
            tag = "[轨迹]" if att.category == "track" else "[照片]"
            if att.exists:
                text = f"{tag} {att.description}"
            else:
                text = f"{tag} {att.description}  ⚠【原始文件缺失】"
            self._add_photo_item(text, True, idx, att.exists)

    def _add_photo_item(self, text: str, checked: bool, attach_idx: int, exists: bool):
        it = QListWidgetItem(text)
        it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
        it.setCheckState(Qt.Checked if checked else Qt.Unchecked)
        it.setData(Qt.UserRole, attach_idx)
        if not exists:
            it.setForeground(QColor("#C62828"))
        self.list_photos.addItem(it)

    def _collect_checked_attachments(self) -> List[dict]:
        result = []
        if not self._record:
            return result
        for i in range(self.list_photos.count()):
            it = self.list_photos.item(i)
            if it.checkState() == Qt.Checked:
                idx = it.data(Qt.UserRole)
                if idx is not None and 0 <= idx < len(self._record.attachments):
                    att = self._record.attachments[idx]
                    result.append({
                        "index": len(result) + 1,
                        "attach_idx": idx,
                        "type": "轨迹截图" if att.category == "track" else "现场照片",
                        "desc": att.description,
                        "category": att.category,
                        "file_path": att.file_path,
                        "exists": att.exists,
                    })
        return result

    RESP_PHASE_NAMES = {
        ResponsibilityPhase.LOADING_SEAL: "① 装货封签阶段",
        ResponsibilityPhase.DEPARTURE_POWER: "② 出发切换冷源阶段",
        ResponsibilityPhase.EQUIPMENT_FAULT: "③ 设备故障阶段",
        ResponsibilityPhase.DRIVER_RESPONSE: "④ 司机响应阶段",
        ResponsibilityPhase.MAINTENANCE_RECOVERY: "⑤ 维修恢复阶段",
        ResponsibilityPhase.NORMAL_TRANSIT: "⑥ 后续在途阶段",
        ResponsibilityPhase.ARRIVAL_ACCEPTANCE: "⑦ 到货验收阶段",
    }

    def _static_evaluate_scheme(self, r: TransportRecord, scheme_name: str, cargo: CargoConfig) -> Optional[dict]:
        from datetime import datetime as _dt
        tmin = cargo.temp_min
        tmax = cargo.temp_max
        tolerance = cargo.tolerance_minutes
        start_dt = r.loading_time
        end_dt = r.unloading_time
        if tmin >= tmax or start_dt is None or end_dt is None or start_dt >= end_dt:
            return None
        in_range = [rd for rd in r.temperature_log if start_dt <= rd.timestamp <= end_dt]
        if not in_range:
            return None
        in_range.sort(key=lambda rd: rd.timestamp)
        exceeded = []
        for rd in in_range:
            if rd.temperature > tmax or rd.temperature < tmin:
                exceeded.append(rd)
        segments = []
        current_seg = []
        for rd in in_range:
            is_exceed = rd.temperature > tmax or rd.temperature < tmin
            if is_exceed:
                current_seg.append(rd)
            elif current_seg:
                seg_start = current_seg[0].timestamp
                seg_end = current_seg[-1].timestamp
                minutes = int((seg_end - seg_start).total_seconds() // 60) + 1
                peak = max(current_seg, key=lambda x: abs(x.temperature - (tmin + tmax) / 2)).temperature
                segments.append((seg_start, seg_end, minutes, peak))
                current_seg = []
        if current_seg:
            seg_start = current_seg[0].timestamp
            seg_end = current_seg[-1].timestamp
            minutes = int((seg_end - seg_start).total_seconds() // 60) + 1
            peak = max(current_seg, key=lambda x: abs(x.temperature - (tmin + tmax) / 2)).temperature
            segments.append((seg_start, seg_end, minutes, peak))
        total_minutes = sum(s[2] for s in segments)
        peak = max(exceeded, key=lambda x: abs(x.temperature - (tmin + tmax) / 2)).temperature if exceeded else None
        is_acceptable = total_minutes <= tolerance
        if is_acceptable and total_minutes == 0:
            conclusion = "温区全程稳定"
            risk = "低"
        elif is_acceptable:
            conclusion = "未超过约定容忍时长"
            risk = "中低"
        else:
            conclusion = "可能影响收货验收"
            risk = "高"
        return {
            "name": scheme_name,
            "cargo": cargo,
            "tmin": tmin,
            "tmax": tmax,
            "tolerance": tolerance,
            "total_minutes": total_minutes,
            "peak": peak,
            "is_acceptable": is_acceptable,
            "conclusion": conclusion,
            "risk": risk,
        }

    def _suggested_action(self, eval_row: dict) -> str:
        if eval_row["is_acceptable"] and eval_row["total_minutes"] == 0:
            return "无异常，归档即可"
        if eval_row["is_acceptable"]:
            return "可正常收货，内部质控记录备案"
        exceed = eval_row["total_minutes"] - eval_row["tolerance"]
        if eval_row["cargo"].cargo_type == CargoType.PHARMACEUTICAL:
            return "立即启动隔离抽检，联系货主按偏差流程处理"
        if exceed <= 30:
            return "与货主协商折扣收货，内部追责司机响应延迟"
        if exceed <= 120:
            return "建议保险立案，同步评估货品品质风险"
        return "高风险拒收/报废，启动保险理赔并保存完整证据链"

    def _build_scheme_comparison(self, r: TransportRecord) -> str:
        if not self.chk_impact.isChecked():
            return ""
        schemes = list(r.temp_schemes or [])
        if r.cargo and not any(
            s.cargo.temp_min == r.cargo.temp_min and s.cargo.temp_max == r.cargo.temp_max
            for s in schemes
        ):
            schemes.append(TempScheme(name="自定义（当前评估）", cargo=r.cargo, scheme_type="自定义"))
        if not schemes:
            return ""
        rows = []
        for s in schemes:
            ev = self._static_evaluate_scheme(r, s.name, s.cargo)
            if ev:
                rows.append(ev)
        if not rows:
            return ""
        lines = []
        lines.append("┌" + "─" * 14 + "┬" + "─" * 10 + "┬" + "─" * 8 + "┬" + "─" * 10 + "┬" + "─" * 16 + "┬" + "─" * 8 + "┬" + "─" * 34 + "┐")
        lines.append("│" + "方案名称".center(14) + "│" + "温区(℃)".center(10) + "│" + "容忍".center(8) + "│" + "越线分钟".center(10) + "│" + "结论".center(16) + "│" + "风险".center(8) + "│" + "建议动作".center(34) + "│")
        lines.append("├" + "─" * 14 + "┼" + "─" * 10 + "┼" + "─" * 8 + "┼" + "─" * 10 + "┼" + "─" * 16 + "┼" + "─" * 8 + "┼" + "─" * 34 + "┤")
        for row in rows:
            name = row["name"][:13]
            temp_range = f"{row['tmin']:.0f}~{row['tmax']:.0f}"
            tol = f"{row['tolerance']}分"
            exceed = f"{row['total_minutes']}分"
            marker = "●" if (row["is_acceptable"] and row["total_minutes"] == 0) else ("▲" if row["is_acceptable"] else "✗")
            concl = f"{marker}{row['conclusion'][:6]}"
            risk = row["risk"]
            act = self._suggested_action(row)[:33]
            lines.append(
                "│" + name.center(14) + "│" + temp_range.center(10) + "│" + tol.center(8) + "│"
                + exceed.center(10) + "│" + concl.center(16) + "│" + risk.center(8) + "│"
                + act.center(34) + "│"
            )
        lines.append("└" + "─" * 14 + "┴" + "─" * 10 + "┴" + "─" * 8 + "┴" + "─" * 10 + "┴" + "─" * 16 + "┴" + "─" * 8 + "┴" + "─" * 34 + "┘")
        lines.append("")
        lines.append("符号说明：● 全程稳定  ▲ 短时越线但可接受  ✗ 超过容忍阈值")
        ok = [r_ for r_ in rows if r_["is_acceptable"]]
        bad = [r_ for r_ in rows if not r_["is_acceptable"]]
        if ok and bad:
            worst = max(bad, key=lambda c: c["total_minutes"])
            best = min(ok, key=lambda c: c["total_minutes"])
            lines.append(f"综合判定：存在口径分歧。最严方案【{worst['name']}】超出容忍 {worst['total_minutes'] - worst['tolerance']} 分钟；最松方案【{best['name']}】尚余 {best['tolerance'] - best['total_minutes']} 分钟。")
            lines.append("建议：优先按货主合同口径与收货方沟通；保险口径同步准备理赔材料，按最坏口径申请。")
        elif bad:
            lines.append("综合判定：所有业务口径均判定越线超过容忍阈值。")
            lines.append("建议：立即启动保险理赔流程，同步联系货主告知风险并安排隔离抽检。")
        elif len(rows) > 1:
            lines.append("综合判定：所有业务口径均判定可接受或温区稳定。")
            lines.append("建议：正常收货归档，内部质控按严格口径考核司机处置时效。")
        return "\n".join(lines)

    def _build_package(self) -> Optional[EvidencePackage]:
        if not self._record:
            QMessageBox.warning(self, "缺少数据", "请先导入运输记录。")
            return None

        recipient_key = self.cmb_recipient.currentData()
        if self.chk_impact.isChecked() and not self._assessment:
            QMessageBox.warning(
                self, "未完成评估",
                "已勾选「温区影响评估结论」，请先在「温区影响估算」面板执行评估，"
                "或取消该选项。"
            )
            return None

        r = self._record
        timeline_summary = self._build_timeline_summary(r)
        responsibility_summary = self._build_responsibility_summary(r)
        impact_summary = self._build_impact_summary(r)
        temp_scheme_comparison = self._build_scheme_comparison(r)
        alert_records = self._build_alert_records(r, recipient_key)
        driver_statement = r.driver_notes if self.chk_driver_statement.isChecked() else ""
        included_attachments = self._collect_checked_attachments() if self.chk_photos.isChecked() else []

        package = EvidencePackage(
            package_title=self.edt_package_title.text().strip() or "冷藏车断电证据包",
            export_time=datetime.now(),
            record_id=r.record_id,
            vehicle_plate=r.vehicle_plate,
            route=f"{r.route_from} → {r.route_to}",
            timeline_summary=timeline_summary,
            impact_summary=impact_summary,
            alert_records=alert_records,
            driver_statement=driver_statement,
            included_attachments=included_attachments,
            responsibility_summary=responsibility_summary,
            temp_scheme_comparison=temp_scheme_comparison,
        )
        return package

    def _build_responsibility_summary(self, r: TransportRecord) -> str:
        if not self.chk_timeline.isChecked():
            return ""
        grouped = r.group_alerts_by_responsibility()
        if not grouped:
            return ""
        lines = []
        lines.append("┌" + "─" * 76 + "┐")
        lines.append("│" + "责任链阶段分组说明".center(76) + "│")
        lines.append("├" + "─" * 76 + "┤")
        for phase, alerts in grouped.items():
            phase_name = self.RESP_PHASE_NAMES.get(phase, phase.value)
            t_start = min(a.timestamp for a in alerts).strftime("%m-%d %H:%M")
            t_end = max(a.timestamp for a in alerts).strftime("%m-%d %H:%M")
            lines.append(f"│ {phase_name:<22} {t_start} ~ {t_end}  共{len(alerts):>2}个节点".ljust(74) + " │")
        lines.append("├" + "─" * 76 + "┤")

        all_alerts = r.sorted_alerts()
        cooler = [a for a in all_alerts if a.alert_type.name == "COOLER_STOP"]
        driver = [a for a in all_alerts if a.alert_type.name == "DRIVER_CONFIRM"]
        restore = [a for a in all_alerts if a.alert_type.name in ("POWER_RESTORE", "COOLER_RESTART")]
        temp_rec = [a for a in all_alerts if a.alert_type.name == "TEMP_RECOVER"]

        lines.append("│" + "关键节点时间差".center(76) + "│")
        lines.append("├" + "─" * 76 + "┤")
        if cooler and driver:
            lag = (driver[0].timestamp - cooler[0].timestamp).total_seconds() / 60
            mark = "✓" if lag <= 10 else "✗"
            lines.append(f"│  {mark}  冷机停转 → 司机首次确认  :  {lag:>6.1f} 分钟（建议 ≤ 10 分钟）".ljust(74) + " │")
        if cooler and restore:
            lag = (restore[0].timestamp - cooler[0].timestamp).total_seconds() / 60
            lines.append(f"│  ●  冷机停转 → 恢复供电成功  :  {lag:>6.1f} 分钟（含支援车程）".ljust(74) + " │")
        if restore and temp_rec:
            lag = (temp_rec[0].timestamp - restore[0].timestamp).total_seconds() / 60
            lines.append(f"│  ●  恢复供电 → 温度回归温区  :  {lag:>6.1f} 分钟（冷机拉温时间）".ljust(74) + " │")
        lines.append("└" + "─" * 76 + "┘")
        return "\n".join(lines)

    def _build_timeline_summary(self, r: TransportRecord) -> str:
        if not self.chk_timeline.isChecked():
            return ""
        alerts = r.sorted_alerts()
        lines = []
        lines.append("┌" + "─" * 76 + "┐")
        lines.append("│" + "告警时间轴汇总（按时间顺序）".center(76) + "│")
        lines.append("├" + "─" * 76 + "┤")
        lines.append(
            "│ " + f"{'时间':<16}{'类型':<14}{'温度':<10}{'操作人':<14}".ljust(74) + " │"
        )
        lines.append("├" + "─" * 76 + "┤")
        for a in alerts:
            t = a.timestamp.strftime("%m-%d %H:%M")
            tp = a.alert_type.value
            temp = f"{a.temperature:.1f}℃" if a.temperature is not None else "—"
            op = a.operator or "—"
            line = f"{t:<16}{tp:<14}{temp:<10}{op:<14}"
            lines.append("│ " + line.ljust(74) + " │")
        lines.append("└" + "─" * 76 + "┘")

        critical = [a for a in alerts if a.severity == AlertSeverity.CRITICAL]
        if len(critical) >= 2:
            a0, a1 = critical[0], critical[-1]
            gap = (a1.timestamp - a0.timestamp).total_seconds() / 60
            lines.append("")
            lines.append(f"【关键时间差】首条严重告警 → 末条严重告警：{gap:.0f} 分钟")

        driver_confirm = [a for a in alerts if a.alert_type.name == "DRIVER_CONFIRM"]
        cooler_stop = [a for a in alerts if a.alert_type.name == "COOLER_STOP"]
        if cooler_stop and driver_confirm:
            lag = (driver_confirm[0].timestamp - cooler_stop[0].timestamp).total_seconds() / 60
            lines.append(f"【响应时效】冷机停转 → 司机首次确认：{lag:.0f} 分钟")
        return "\n".join(lines)

    def _build_impact_summary(self, r: TransportRecord) -> str:
        if not self.chk_impact.isChecked():
            return ""
        if not self._assessment or not r.cargo:
            return "（未执行温区影响评估）"
        a = self._assessment
        c = r.cargo
        lines = []
        lines.append("═" * 80)
        lines.append("温区影响评估结论".center(80))
        lines.append("═" * 80)
        lines.append(f"货品：{c.cargo_name}（{c.cargo_type.value}）")
        lines.append(f"约定温区：{c.temp_min:.1f}℃ ~ {c.temp_max:.1f}℃　容忍越线：{a.tolerance_minutes} 分钟")
        lines.append(f"越线时段：{a.affected_period}")
        lines.append(f"实际越线时长：{a.exceed_duration_minutes} 分钟")
        lines.append("")
        marker = "●" if a.is_acceptable else "✗"
        lines.append(f"最终结论：{marker} {a.conclusion}　风险等级：【{a.risk_level}】")
        lines.append("")
        lines.append("评估摘要：")
        lines.extend("  " + ln for ln in a.detail.splitlines()[:12])
        return "\n".join(lines)

    def _build_alert_records(self, r: TransportRecord, recipient_key: str) -> List[str]:
        if not self.chk_alerts.isChecked():
            return []
        lines = []
        lines.append("序号,时间,告警类型,严重度,描述,温度(℃),操作人,地点")
        for i, a in enumerate(r.sorted_alerts(), 1):
            fields = [
                str(i),
                a.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                a.alert_type.value,
                a.severity.name,
                '"' + a.description.replace('"', "''") + '"',
                f"{a.temperature:.1f}" if a.temperature is not None else "",
                a.operator or "",
                '"' + (a.location or "").replace('"', "''") + '"',
            ]
            lines.append(",".join(fields))
        return lines

    def _build_preview_text(self, p: EvidencePackage) -> str:
        parts = []
        parts.append("=" * 78)
        parts.append(p.package_title.center(78))
        parts.append("=" * 78)
        parts.append(f"生成时间：{p.export_time.strftime('%Y-%m-%d %H:%M:%S')}")
        parts.append(f"运输编号：{p.record_id}　　车牌：{p.vehicle_plate}")
        parts.append(f"运输路线：{p.route}")
        parts.append(f"发送对象：{self.cmb_recipient.currentText()}")
        parts.append(f"打包为ZIP：{'是' if self.chk_zip.isChecked() else '否'}")
        parts.append("")

        if p.responsibility_summary:
            parts.append(">>> 〇、责任链阶段分组说明")
            parts.append(p.responsibility_summary)
            parts.append("")
        if p.timeline_summary:
            parts.append(">>> 一、告警时间轴汇总")
            parts.append(p.timeline_summary)
            parts.append("")
        if p.impact_summary:
            parts.append(">>> 二、温区影响评估结论")
            parts.append(p.impact_summary)
            parts.append("")
        if p.temp_scheme_comparison:
            parts.append(">>> 二-一、多方案温区对比摘要（含建议动作）")
            parts.append(p.temp_scheme_comparison)
            parts.append("")
        if p.alert_records:
            parts.append(">>> 三、完整告警记录（CSV）")
            parts.extend(p.alert_records[:12])
            if len(p.alert_records) > 12:
                parts.append(f"... 以下省略 {len(p.alert_records) - 12} 行，导出时包含全部 ...")
            parts.append("")
        if p.driver_statement:
            parts.append(">>> 四、司机书面处置说明")
            parts.append(p.driver_statement)
            parts.append("")
        if p.included_attachments:
            parts.append(">>> 五、附件清单（照片 / 轨迹截图）")
            missing_count = 0
            for att in p.included_attachments:
                status = "" if att["exists"] else "  ⚠【原始文件缺失，无法导出】"
                if not att["exists"]:
                    missing_count += 1
                parts.append(f"  {att['index']:>2}. [{att['type']}] {att['desc']}{status}")
            if missing_count:
                parts.append(f"  （共 {len(p.included_attachments)} 项，其中 {missing_count} 项原始文件缺失，缺失项将在报告中醒目标注）")
            parts.append("")
        if self.chk_temp_log.isChecked() and self._record:
            parts.append(">>> 六、温度日志明细（CSV 文件）")
            parts.append(f"  包含 {len(self._record.temperature_log)} 条分钟级温度数据。")
            parts.append(f"  导出文件名：{p.record_id}_temperature_log.csv")
            parts.append("")
        parts.append("─" * 78)
        parts.append("本证据包由「冷藏车断电复盘工具」自动生成，所有时间、温度、操作记录均来自车载终端原始数据。")
        return "\n".join(parts)

    def _build_preview(self):
        pkg = self._build_package()
        if not pkg:
            return
        self.lbl_preview_title.setText(pkg.package_title)
        self.lbl_preview_meta.setText(
            f"运输编号 {pkg.record_id}　|　车牌 {pkg.vehicle_plate}　|　"
            f"生成于 {pkg.export_time.strftime('%H:%M:%S')}"
        )
        self.txt_preview.setPlainText(self._build_preview_text(pkg))

    def _export_package(self):
        pkg = self._build_package()
        if not pkg:
            return

        default_dir = os.path.join(os.path.expanduser("~"), "Documents")
        default_name = pkg.package_title
        out_dir = QFileDialog.getExistingDirectory(
            self, "选择证据包导出目录", default_dir
        )
        if not out_dir:
            return

        try:
            self.progress.setVisible(True)
            self.progress.setValue(8)

            pkg_dir = os.path.join(out_dir, default_name)
            os.makedirs(pkg_dir, exist_ok=True)
            attachments_dir = os.path.join(pkg_dir, "attachments")
            os.makedirs(attachments_dir, exist_ok=True)

            base = os.path.join(pkg_dir, default_name)

            self.progress.setValue(20)
            exported_attachments = []
            missing_attachments = []
            if self.chk_photos.isChecked() and pkg.included_attachments:
                total = len(pkg.included_attachments)
                for i, att in enumerate(pkg.included_attachments, 1):
                    idx = att["index"]
                    cat = att["category"]
                    desc = att["desc"]
                    exists = att["exists"]
                    src_path = att["file_path"]
                    tag = "轨迹" if cat == "track" else "照片"
                    safe_desc = self._sanitize_filename(desc)
                    ext = ".png" if cat == "track" else ".jpg"
                    safe_name = f"{tag}_{idx:02d}_{safe_desc}{ext}"
                    dst_full = os.path.join(attachments_dir, safe_name)
                    rel_path = f"attachments/{safe_name}"

                    if exists and src_path and os.path.isfile(src_path):
                        shutil.copyfile(src_path, dst_full)
                        exported_attachments.append({
                            "index": idx,
                            "type": att["type"],
                            "desc": desc,
                            "filename": rel_path,
                            "exists": True,
                        })
                    else:
                        missing_attachments.append({
                            "index": idx,
                            "type": att["type"],
                            "desc": desc,
                            "orig_path": src_path or "(原始路径未记录)",
                        })
                        exported_attachments.append({
                            "index": idx,
                            "type": att["type"],
                            "desc": desc,
                            "filename": None,
                            "exists": False,
                            "orig_path": src_path or "(原始路径未记录)",
                        })
                    self.progress.setValue(20 + int(35 * i / max(1, total)))

            readme_path = base + "_证据包说明.md"
            self.progress.setValue(62)
            with open(readme_path, "w", encoding="utf-8") as f:
                f.write(self._build_readme_content(pkg, exported_attachments))

            self.progress.setValue(72)
            csv_path = None
            if pkg.alert_records:
                csv_path = base + "_告警记录.csv"
                with open(csv_path, "w", encoding="utf-8-sig") as f:
                    f.write("\n".join(pkg.alert_records) + "\n")

            self.progress.setValue(82)
            tlog_path = None
            if self.chk_temp_log.isChecked() and self._record:
                tlog_path = base + "_温度日志.csv"
                with open(tlog_path, "w", encoding="utf-8-sig") as f:
                    f.write("时间,温度(℃),温区\n")
                    for r in self._record.temperature_log:
                        f.write(
                            f"{r.timestamp.strftime('%Y-%m-%d %H:%M:%S')},"
                            f"{r.temperature:.1f},{r.zone}\n"
                        )

            self.progress.setValue(90)
            driver_path = None
            if pkg.driver_statement:
                driver_path = base + "_司机处置说明.txt"
                with open(driver_path, "w", encoding="utf-8") as f:
                    f.write(
                        f"运输编号：{pkg.record_id}\n"
                        f"车牌：{pkg.vehicle_plate}\n"
                        f"司机：{self._record.driver_name if self._record else ''}\n"
                        f"路线：{pkg.route}\n"
                        f"生成时间：{pkg.export_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                        + "─" * 50 + "\n\n"
                        + pkg.driver_statement
                    )

            self.progress.setValue(94)

            zip_path = None
            if self.chk_zip.isChecked():
                plate_clean = pkg.vehicle_plate.replace("·", "").replace("·", "")
                zip_name = f"{pkg.record_id}_{plate_clean}_证据包.zip"
                zip_path = os.path.join(out_dir, zip_name)
                with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                    for root, _, files in os.walk(pkg_dir):
                        for fn in files:
                            full = os.path.join(root, fn)
                            arc = os.path.relpath(full, pkg_dir)
                            zf.write(full, arcname=os.path.join(default_name, arc))

            self.progress.setValue(100)
            file_list = [f"  • {os.path.basename(readme_path)}（主文件，双击打开）\n"]
            if csv_path:
                file_list.append(f"  • {os.path.basename(csv_path)}\n")
            if tlog_path:
                file_list.append(f"  • {os.path.basename(tlog_path)}\n")
            if driver_path:
                file_list.append(f"  • {os.path.basename(driver_path)}\n")
            if exported_attachments:
                ok_count = sum(1 for a in exported_attachments if a["exists"])
                miss_count = len(exported_attachments) - ok_count
                if miss_count:
                    file_list.append(f"  • attachments/  （实有 {ok_count} 张，缺失 {miss_count} 项，缺失项在说明文件中标红）\n")
                else:
                    file_list.append(f"  • attachments/  （含 {ok_count} 张照片/截图）\n")
            if zip_path:
                file_list.insert(0, f"\n  ZIP 压缩包：{zip_name}\n")

            msg = f"证据包已导出至：\n{pkg_dir}\n\n包含文件：\n" + "".join(file_list)
            if missing_attachments:
                msg += f"\n⚠ 缺失 {len(missing_attachments)} 个附件原始文件，已在 Markdown 报告中醒目标注。\n"
            if zip_path:
                msg += f"\nZIP 打包完成：\n{zip_path}\n（可直接邮件/微信发送）"

            QMessageBox.information(self, "导出成功", msg)
        except Exception as e:
            QMessageBox.critical(self, "导出失败", f"导出过程中发生错误：\n{e}")
        finally:
            self.progress.setVisible(False)
            self.progress.setValue(0)

    def _sanitize_filename(self, name: str) -> str:
        invalid = '<>:"/\\|?*'
        for ch in invalid:
            name = name.replace(ch, "_")
        return name.strip().replace(" ", "_")[:60]

    def _build_readme_content(self, p: EvidencePackage, included_image_files: List[dict] = None) -> str:
        lines = []
        lines.append(f"# {p.package_title}")
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## 一、基本信息")
        lines.append("")
        lines.append(f"- **运输编号**：{p.record_id}")
        lines.append(f"- **车牌号码**：{p.vehicle_plate}")
        lines.append(f"- **运输路线**：{p.route}")
        lines.append(f"- **发送对象**：{self.cmb_recipient.currentText()}")
        lines.append(f"- **导出时间**：{p.export_time.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"- **生成工具**：冷藏车断电复盘桌面工具 v1.0")
        lines.append("")
        if p.responsibility_summary:
            lines.append("## 二、责任链阶段分组说明")
            lines.append("")
            lines.append("```")
            lines.append(p.responsibility_summary)
            lines.append("```")
            lines.append("")
        if p.timeline_summary:
            lines.append("## 三、告警时间轴汇总")
            lines.append("")
            lines.append("```")
            lines.append(p.timeline_summary)
            lines.append("```")
            lines.append("")
        if p.impact_summary:
            lines.append("## 四、温区影响评估结论")
            lines.append("")
            lines.append("```")
            lines.append(p.impact_summary)
            lines.append("```")
            lines.append("")
        if p.temp_scheme_comparison:
            lines.append("## 四-一、多方案温区对比摘要（含建议动作）")
            lines.append("")
            lines.append("> 同一趟运输按照「货主合同 / 保险条款 / 内部质控」等多套业务口径的对比，")
            lines.append("> 用于收货沟通、保险理赔、内部追责时快速说明各方差异，不用截图反复解释。")
            lines.append("")
            lines.append("```")
            lines.append(p.temp_scheme_comparison)
            lines.append("```")
            lines.append("")
        if p.driver_statement:
            lines.append("## 五、司机书面处置说明")
            lines.append("")
            lines.append("> 注：完整文本见同目录 `*_司机处置说明.txt`。")
            lines.append("")
            lines.append("```")
            lines.append(p.driver_statement)
            lines.append("```")
            lines.append("")
        if included_image_files:
            ok_count = sum(1 for a in included_image_files if a["exists"])
            miss_count = len(included_image_files) - ok_count
            lines.append("## 六、附件清单（现场照片 / 轨迹截图）")
            lines.append("")
            if miss_count:
                lines.append(f"> <span style=\"color:#C62828;font-weight:600;\">**注意**：共 {len(included_image_files)} 项附件，其中 **{miss_count} 项原始文件缺失**，已在下表中用红色醒目标注。请尽快向车队或司机索取原始文件补全。</span>")
                lines.append("")
            lines.append("| 序号 | 类型 | 附件状态 | 说明 | 链接 |")
            lines.append("| --- | --- | --- | --- | --- |")
            for img in included_image_files:
                idx = img["index"]
                tag = img["type"]
                desc = img["desc"]
                if img["exists"] and img["filename"]:
                    rel_path = img["filename"].replace("\\", "/")
                    status_cell = "✅ 已导出"
                    link_cell = f"[点击打开原图]({rel_path})"
                    desc_cell = desc
                else:
                    orig = img.get("orig_path", "(原始路径未记录)")
                    status_cell = "<span style=\"color:#C62828;font-weight:700;\">❌ 文件缺失</span>"
                    desc_cell = f"<span style=\"color:#C62828;\">{desc}　**【原始文件缺失，请向相关人员索取补全】**</span>"
                    link_cell = f"<span style=\"color:#C62828;\">原始路径：`{orig}`</span>"
                lines.append(f"| {idx} | {tag} | {status_cell} | {desc_cell} | {link_cell} |")
            lines.append("")
            if ok_count:
                lines.append("> **使用说明**：表格中状态为「✅ 已导出」的附件，其原图已复制到 `attachments/` 目录，点击蓝色链接可直接打开。")
            if miss_count:
                lines.append("")
                lines.append("> **缺失项说明**：标记为「❌ 文件缺失」的附件，在当前系统中未找到对应原始文件，可能原因：拍摄后未上传、存储路径变更、硬盘介质损坏等。建议在发送证据包前，联系车队/司机补充缺失的现场照片。")
            lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("> **备注**：本证据包所有数据均来自车载终端原始记录，")
        lines.append("> 时间戳与温度值不可篡改。如需进一步核验，请联系车队质控部门调取原始 SDD 日志文件。")
        return "\n".join(lines)
