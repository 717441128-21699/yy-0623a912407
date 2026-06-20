from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional, Tuple, Dict


class AlertType(Enum):
    POWER_DISCONNECT = "外接电断开"
    COOLER_STOP = "冷机停转"
    TEMP_EXCEED = "温度越线"
    DRIVER_CONFIRM = "司机确认"
    POWER_RESTORE = "恢复供电"
    COOLER_RESTART = "冷机重启"
    TEMP_RECOVER = "温度恢复正常"
    LOADING = "装货完成"
    UNLOADING = "到达卸货地"


class AlertSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class CargoType(Enum):
    FROZEN = "冷冻货品（-18℃及以下）"
    CHILLED = "冷藏货品（0~8℃）"
    MEDICAL = "医药冷链（2~8℃）"
    FRESH = "生鲜果蔬（4~12℃）"
    SPECIAL = "特殊温区货品"


class ResponsibilityPhase(Enum):
    LOADING_SEAL = "装货封签阶段"
    DEPARTURE_POWER = "出发切换冷源阶段"
    EQUIPMENT_FAULT = "设备故障阶段"
    DRIVER_RESPONSE = "司机响应阶段"
    MAINTENANCE_RECOVERY = "维修恢复阶段"
    NORMAL_TRANSIT = "后续在途阶段"
    ARRIVAL_ACCEPTANCE = "到货验收阶段"


@dataclass
class AlertEvent:
    timestamp: datetime
    alert_type: AlertType
    severity: AlertSeverity
    description: str
    temperature: Optional[float] = None
    operator: Optional[str] = None
    location: Optional[str] = None


@dataclass
class TemperatureReading:
    timestamp: datetime
    temperature: float
    zone: str = "default"


@dataclass
class CargoConfig:
    cargo_type: CargoType
    cargo_name: str
    temp_min: float
    temp_max: float
    tolerance_minutes: int
    shipment_weight: float = 0.0
    shipment_value: float = 0.0


@dataclass
class TempScheme:
    name: str
    cargo: CargoConfig
    description: str = ""
    scheme_type: str = "自定义"  # 货主合同 / 保险条款 / 内部质控 / 自定义


@dataclass
class EvidenceAttachment:
    description: str
    category: str  # "track" 轨迹 / "photo" 照片
    file_path: Optional[str] = None  # 绝对路径；None 表示缺失
    exists: bool = False


@dataclass
class TransportRecord:
    record_id: str
    vehicle_plate: str
    driver_name: str
    route_from: str
    route_to: str
    departure_time: datetime
    arrival_time: Optional[datetime] = None
    loading_time: Optional[datetime] = None
    unloading_time: Optional[datetime] = None
    cargo: Optional[CargoConfig] = None
    alerts: List[AlertEvent] = field(default_factory=list)
    temperature_log: List[TemperatureReading] = field(default_factory=list)
    driver_notes: str = ""
    attachments: List[EvidenceAttachment] = field(default_factory=list)
    temp_schemes: List[TempScheme] = field(default_factory=list)

    def sorted_alerts(self) -> List[AlertEvent]:
        return sorted(self.alerts, key=lambda a: a.timestamp)

    def group_alerts_by_responsibility(self) -> Dict[ResponsibilityPhase, List[AlertEvent]]:
        groups = {p: [] for p in ResponsibilityPhase}
        alerts = self.sorted_alerts()
        if not alerts:
            return groups

        phase_start = {
            ResponsibilityPhase.EQUIPMENT_FAULT: None,
            ResponsibilityPhase.MAINTENANCE_RECOVERY: None,
            ResponsibilityPhase.ARRIVAL_ACCEPTANCE: None,
        }

        for a in alerts:
            if a.alert_type == AlertType.LOADING:
                groups[ResponsibilityPhase.LOADING_SEAL].append(a)
                continue
            if a.alert_type == AlertType.POWER_DISCONNECT and a.timestamp <= (self.loading_time or a.timestamp) + timedelta_10min():
                groups[ResponsibilityPhase.DEPARTURE_POWER].append(a)
                continue
            if a.alert_type in (AlertType.COOLER_STOP, AlertType.TEMP_EXCEED) and phase_start[ResponsibilityPhase.EQUIPMENT_FAULT] is None:
                phase_start[ResponsibilityPhase.EQUIPMENT_FAULT] = a.timestamp
            if a.alert_type in (AlertType.POWER_RESTORE, AlertType.COOLER_RESTART) and phase_start[ResponsibilityPhase.MAINTENANCE_RECOVERY] is None:
                phase_start[ResponsibilityPhase.MAINTENANCE_RECOVERY] = a.timestamp
            if a.alert_type in (AlertType.UNLOADING,):
                phase_start[ResponsibilityPhase.ARRIVAL_ACCEPTANCE] = a.timestamp

        eq_start = phase_start[ResponsibilityPhase.EQUIPMENT_FAULT]
        main_start = phase_start[ResponsibilityPhase.MAINTENANCE_RECOVERY]
        arr_start = phase_start[ResponsibilityPhase.ARRIVAL_ACCEPTANCE]

        for a in alerts:
            if a in groups[ResponsibilityPhase.LOADING_SEAL] or a in groups[ResponsibilityPhase.DEPARTURE_POWER]:
                continue
            t = a.timestamp
            if arr_start and t >= arr_start:
                groups[ResponsibilityPhase.ARRIVAL_ACCEPTANCE].append(a)
                continue
            if a.alert_type == AlertType.DRIVER_CONFIRM:
                groups[ResponsibilityPhase.DRIVER_RESPONSE].append(a)
                continue
            if main_start and t >= main_start:
                groups[ResponsibilityPhase.MAINTENANCE_RECOVERY].append(a)
                continue
            if eq_start and t >= eq_start:
                groups[ResponsibilityPhase.EQUIPMENT_FAULT].append(a)
                continue
            if main_start and eq_start and eq_start <= t < main_start:
                groups[ResponsibilityPhase.EQUIPMENT_FAULT].append(a)
                continue
            if main_start and arr_start and main_start <= t < arr_start:
                if a.alert_type == AlertType.TEMP_RECOVER:
                    groups[ResponsibilityPhase.NORMAL_TRANSIT].append(a)
                else:
                    groups[ResponsibilityPhase.MAINTENANCE_RECOVERY].append(a)
                continue
            groups[ResponsibilityPhase.NORMAL_TRANSIT].append(a)

        non_empty = [(k, v) for k, v in groups.items() if v]
        non_empty.sort(key=lambda kv: min(a.timestamp for a in kv[1]))
        from collections import OrderedDict
        return OrderedDict(non_empty)


def timedelta_10min():
    from datetime import timedelta
    return timedelta(minutes=10)


@dataclass
class ImpactAssessment:
    is_acceptable: bool
    exceed_duration_minutes: int
    tolerance_minutes: int
    peak_temperature: float
    temp_min: float
    temp_max: float
    affected_period: str
    conclusion: str
    detail: str
    risk_level: str
    scheme_name: str = ""


@dataclass
class EvidencePackage:
    package_title: str
    export_time: datetime
    record_id: str
    vehicle_plate: str
    route: str
    timeline_summary: str
    impact_summary: str
    alert_records: List[str]
    driver_statement: str
    included_attachments: List[dict] = field(default_factory=list)
    responsibility_summary: str = ""
    temp_scheme_comparison: str = ""
    responsibility_conclusion: str = ""
    primary_scheme_name: str = ""
    report_purpose: str = "custom"
