import random
from datetime import datetime, timedelta
from .models import (
    TransportRecord, AlertEvent, AlertType, AlertSeverity,
    CargoConfig, CargoType, TemperatureReading
)


def generate_sample_record() -> TransportRecord:
    record_id = f"TR{datetime.now().strftime('%Y%m%d')}-0872"
    vehicle_plate = "沪A·F8523冷"
    driver_name = "张建国"
    route_from = "上海·奉贤冷链中心"
    route_to = "杭州·余杭生鲜仓"

    departure = datetime.now().replace(hour=22, minute=15, second=0, microsecond=0) - timedelta(days=1)
    arrival = departure + timedelta(hours=4, minutes=50)
    loading_time = departure - timedelta(minutes=35)
    unloading_time = arrival + timedelta(minutes=20)

    base_time = departure + timedelta(minutes=55)

    alerts = [
        AlertEvent(
            timestamp=loading_time,
            alert_type=AlertType.LOADING,
            severity=AlertSeverity.INFO,
            description="装货完成，车厢预冷至-22.3℃，开始封签",
            temperature=-22.3,
            operator="调度·李明",
            location=route_from
        ),
        AlertEvent(
            timestamp=departure,
            alert_type=AlertType.POWER_DISCONNECT,
            severity=AlertSeverity.INFO,
            description="车辆出发，外接市电断开，切换车载柴油冷机模式",
            temperature=-22.1,
            operator=driver_name,
            location="上海·S4高速入口"
        ),
        AlertEvent(
            timestamp=base_time,
            alert_type=AlertType.COOLER_STOP,
            severity=AlertSeverity.CRITICAL,
            description="冷机异常停机！ ECU报故障码P0216（燃油喷射正时）",
            temperature=-20.7,
            operator=driver_name,
            location="沪昆高速·嘉兴段K128"
        ),
        AlertEvent(
            timestamp=base_time + timedelta(minutes=18),
            alert_type=AlertType.TEMP_EXCEED,
            severity=AlertSeverity.CRITICAL,
            description="车厢温度-17.8℃ 已越线（约定≤-18℃）",
            temperature=-17.8,
            operator=driver_name,
            location="沪昆高速·嘉兴段K135"
        ),
        AlertEvent(
            timestamp=base_time + timedelta(minutes=22),
            alert_type=AlertType.DRIVER_CONFIRM,
            severity=AlertSeverity.WARNING,
            description="司机确认告警：已安全停靠紧急停车带，尝试重启冷机",
            temperature=-17.2,
            operator=driver_name,
            location="沪昆高速·嘉兴服务区方向"
        ),
        AlertEvent(
            timestamp=base_time + timedelta(minutes=38),
            alert_type=AlertType.DRIVER_CONFIRM,
            severity=AlertSeverity.WARNING,
            description="司机报告：三次重启失败，怀疑燃油滤芯堵塞，已联系就近维修站",
            temperature=-15.4,
            operator=driver_name,
            location="沪昆高速·嘉兴段K142"
        ),
        AlertEvent(
            timestamp=base_time + timedelta(minutes=72),
            alert_type=AlertType.POWER_RESTORE,
            severity=AlertSeverity.INFO,
            description="维修人员抵达，临时外接应急发电机供电",
            temperature=-11.3,
            operator="维修·王师傅",
            location="沪昆高速·长安服务区"
        ),
        AlertEvent(
            timestamp=base_time + timedelta(minutes=78),
            alert_type=AlertType.COOLER_RESTART,
            severity=AlertSeverity.WARNING,
            description="冷机恢复运转，开始全力制冷，当前设定-25℃",
            temperature=-10.8,
            operator="维修·王师傅",
            location="沪昆高速·长安服务区"
        ),
        AlertEvent(
            timestamp=base_time + timedelta(minutes=165),
            alert_type=AlertType.TEMP_RECOVER,
            severity=AlertSeverity.INFO,
            description="车厢温度回归-18.5℃，恢复至约定温区范围",
            temperature=-18.5,
            operator=driver_name,
            location="沪昆高速·杭州段K196"
        ),
        AlertEvent(
            timestamp=arrival,
            alert_type=AlertType.UNLOADING,
            severity=AlertSeverity.INFO,
            description="到达目的地，等待收货仓验收",
            temperature=-20.1,
            operator=driver_name,
            location=route_to
        ),
        AlertEvent(
            timestamp=unloading_time,
            alert_type=AlertType.POWER_DISCONNECT,
            severity=AlertSeverity.INFO,
            description="卸货作业，外接市电连接前短暂断电（约3分钟）",
            temperature=-20.0,
            operator="仓管·陈伟",
            location=route_to
        ),
    ]

    temp_log = _generate_temperature_log(departure, unloading_time, base_time)

    cargo = CargoConfig(
        cargo_type=CargoType.FROZEN,
        cargo_name="进口阿根廷牛肉（冷冻去骨牛腩）",
        temp_min=-25.0,
        temp_max=-18.0,
        tolerance_minutes=45,
        shipment_weight=12800.0,
        shipment_value=486400.0
    )

    driver_notes = (
        "22:15 从奉贤冷链中心准时出发，全程沪昆高速。\n"
        "约23:10行驶至嘉兴段K128时冷机突然停机，仪表显示故障码P0216。\n"
        "立即靠右侧紧急停车带，尝试三次手动重启均失败（每次启动2-3秒即停）。\n"
        "23:47致电公司调度中心说明情况，同时通过APP确认告警信息。\n"
        "次日00:33维修人员带应急发电机抵达长安服务区，外接供电后冷机恢复工作。\n"
        "期间车厢外环境温度约26℃，车厢保温层完好，无开门作业。\n"
        "冷机恢复后设置-25℃全力制冷，02:58温度回落到-18.5℃。\n"
        "03:05安全抵达余杭生鲜仓，全程无超速、无违规驾驶行为。"
    )

    record = TransportRecord(
        record_id=record_id,
        vehicle_plate=vehicle_plate,
        driver_name=driver_name,
        route_from=route_from,
        route_to=route_to,
        departure_time=departure,
        arrival_time=arrival,
        loading_time=loading_time,
        unloading_time=unloading_time,
        cargo=cargo,
        alerts=alerts,
        temperature_log=temp_log,
        driver_notes=driver_notes,
        track_images=[
            "行驶轨迹：上海奉贤→沪昆高速→杭州余杭（全程178km）",
            "关键节点1：嘉兴段K128冷机停机点",
            "关键节点2：长安服务区维修供电点",
        ],
        photo_paths=[
            "冷机故障仪表盘照片",
            "车厢内部温度记录仪照片",
            "维修现场外接发电机照片",
            "到货时货品外观抽检照片",
        ]
    )

    return record


def _generate_temperature_log(start: datetime, end: datetime, incident_start: datetime) -> list:
    readings = []
    current = start
    incident_base = incident_start

    while current <= end:
        diff_min = (current - incident_base).total_seconds() / 60

        if diff_min < 55:
            temp = -22.0 + random.uniform(-0.8, 0.8)
        elif diff_min < 72:
            temp = -20.7 + (diff_min - 55) * 0.19 + random.uniform(-0.3, 0.3)
        elif diff_min < 78:
            temp = -11.3 + random.uniform(-0.5, 0.5)
        elif diff_min < 243:
            t_ratio = (diff_min - 78) / 165
            temp = -10.8 + (-18.5 - (-10.8)) * t_ratio + random.uniform(-0.4, 0.4)
        else:
            temp = -20.0 + random.uniform(-1.0, 1.0)

        readings.append(TemperatureReading(
            timestamp=current,
            temperature=round(temp, 1),
            zone="主货厢"
        ))
        current += timedelta(minutes=1)

    return readings
