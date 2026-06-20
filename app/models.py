from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional


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
    track_images: List[str] = field(default_factory=list)
    driver_notes: str = ""
    photo_paths: List[str] = field(default_factory=list)

    def sorted_alerts(self) -> List[AlertEvent]:
        return sorted(self.alerts, key=lambda a: a.timestamp)


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
    included_images: List[str]
