import os
from datetime import datetime
from typing import Optional, List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton,
    QComboBox, QLineEdit, QCheckBox, QListWidget, QListWidgetItem,
    QTextEdit, QFileDialog, QMessageBox, QGroupBox, QFormLayout,
    QSizePolicy, QProgressBar
)

from .models import TransportRecord, ImpactAssessment, EvidencePackage, AlertSeverity


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
        for item in self._record.track_images:
            self._add_photo_item(f"[轨迹] {item}", True)
        for item in self._record.photo_paths:
            self._add_photo_item(f"[照片] {item}", True)

    def _add_photo_item(self, text: str, checked: bool):
        it = QListWidgetItem(text)
        it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
        it.setCheckState(Qt.Checked if checked else Qt.Unchecked)
        self.list_photos.addItem(it)

    def _collect_checked_photos(self) -> List[str]:
        result = []
        for i in range(self.list_photos.count()):
            it = self.list_photos.item(i)
            if it.checkState() == Qt.Checked:
                result.append(it.text())
        return result

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
        impact_summary = self._build_impact_summary(r)
        alert_records = self._build_alert_records(r, recipient_key)
        driver_statement = r.driver_notes if self.chk_driver_statement.isChecked() else ""
        included_images = self._collect_checked_photos() if self.chk_photos.isChecked() else []

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
            included_images=included_images,
        )
        return package

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
        parts.append("")

        if p.timeline_summary:
            parts.append(">>> 一、告警时间轴汇总")
            parts.append(p.timeline_summary)
            parts.append("")
        if p.impact_summary:
            parts.append(">>> 二、温区影响评估结论")
            parts.append(p.impact_summary)
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
        if p.included_images:
            parts.append(">>> 五、附件清单（照片 / 轨迹截图）")
            for i, name in enumerate(p.included_images, 1):
                parts.append(f"  {i:>2}. {name}")
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
            self.progress.setValue(10)

            os.makedirs(out_dir, exist_ok=True)
            base = os.path.join(out_dir, default_name)

            readme_path = base + "_证据包说明.md"
            self.progress.setValue(30)
            with open(readme_path, "w", encoding="utf-8") as f:
                f.write(self._build_readme_content(pkg))

            self.progress.setValue(55)
            if pkg.alert_records:
                csv_path = base + "_告警记录.csv"
                with open(csv_path, "w", encoding="utf-8-sig") as f:
                    f.write("\n".join(pkg.alert_records) + "\n")

            self.progress.setValue(75)
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
            driver_path = base + "_司机处置说明.txt"
            if pkg.driver_statement:
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

            self.progress.setValue(100)
            QMessageBox.information(
                self, "导出成功",
                f"证据包已导出至：\n{out_dir}\n\n"
                f"包含文件：\n"
                f"  • {os.path.basename(readme_path)}（主文件，可直接发送）\n"
                + (f"  • {os.path.basename(csv_path)}\n" if pkg.alert_records else "")
                + (f"  • {os.path.basename(tlog_path)}\n" if self.chk_temp_log.isChecked() and self._record else "")
                + (f"  • {os.path.basename(driver_path)}\n" if pkg.driver_statement else "")
            )
        except Exception as e:
            QMessageBox.critical(self, "导出失败", f"导出过程中发生错误：\n{e}")
        finally:
            self.progress.setVisible(False)
            self.progress.setValue(0)

    def _build_readme_content(self, p: EvidencePackage) -> str:
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
        if p.timeline_summary:
            lines.append("## 二、告警时间轴汇总")
            lines.append("")
            lines.append("```")
            lines.append(p.timeline_summary)
            lines.append("```")
            lines.append("")
        if p.impact_summary:
            lines.append("## 三、温区影响评估结论")
            lines.append("")
            lines.append("```")
            lines.append(p.impact_summary)
            lines.append("```")
            lines.append("")
        if p.driver_statement:
            lines.append("## 四、司机书面处置说明")
            lines.append("")
            lines.append("> 注：完整文本见同目录 `*_司机处置说明.txt`。")
            lines.append("")
            lines.append("```")
            lines.append(p.driver_statement)
            lines.append("```")
            lines.append("")
        if p.included_images:
            lines.append("## 五、附件清单")
            lines.append("")
            lines.append("| 序号 | 附件类型 | 说明 |")
            lines.append("| --- | --- | --- |")
            for i, name in enumerate(p.included_images, 1):
                tag = "照片" if name.startswith("[照片]") else "轨迹"
                desc = name.replace("[照片] ", "").replace("[轨迹] ", "")
                lines.append(f"| {i} | {tag} | {desc} |")
            lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("> **备注**：本证据包所有数据均来自车载终端原始记录，")
        lines.append("> 时间戳与温度值不可篡改。如需进一步核验，请联系车队质控部门调取原始 SDD 日志文件。")
        return "\n".join(lines)
