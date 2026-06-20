import os, sys
from PySide6.QtGui import QPixmap, QPainter, QColor, QFont, QPen, QBrush
from PySide6.QtWidgets import QApplication
from datetime import datetime

app = QApplication.instance() or QApplication(sys.argv)

out_dir = os.path.join(os.getcwd(), '_sample_photos')
os.makedirs(out_dir, exist_ok=True)

date_str = datetime.now().strftime('%Y%m%d')
plate = '沪AF8523冷'
rec = 'TR{}-0872'.format(date_str)


def make_img(path, title, subtitle, color_top, color_body):
    pix = QPixmap(1280, 720)
    pix.fill(QColor(color_body))
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(QPen(QColor(color_top), 0))
    p.setBrush(QBrush(QColor(color_top)))
    p.drawRect(0, 0, 1280, 90)
    p.setPen(QPen(QColor('white')))
    p.setFont(QFont('Microsoft YaHei', 26, QFont.Bold))
    p.drawText(30, 60, title)
    p.setFont(QFont('Microsoft YaHei', 13))
    p.drawText(880, 60, '{}  |  {}'.format(plate, date_str))
    p.setPen(QPen(QColor('#37474F')))
    p.setFont(QFont('Microsoft YaHei', 18))
    y = 180
    for ln in subtitle.split('\n'):
        p.drawText(60, y, ln)
        y += 34
    p.setPen(QPen(QColor('#B0BEC5')))
    p.drawRect(60, 280, 1160, 360)
    p.setPen(QPen(QColor('#CFD8DC')))
    for yy in range(280, 641, 72):
        p.drawLine(60, yy, 1220, yy)
    for xx in range(60, 1221, 116):
        p.drawLine(xx, 280, xx, 640)
    p.setPen(QPen(QColor('#90A4AE')))
    p.setFont(QFont('Consolas', 10))
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    p.drawText(60, 680, 'Generated: {}    Source: ColdChain Review Tool'.format(ts))
    p.end()
    pix.save(path)


existing = [
    ('track_overview', '行驶轨迹总览',
     '上海奉贤 -> 沪昆高速 -> 杭州余杭  全程 178km\n出发 22:15    预计到达 03:05\n异常点：嘉兴段K128（冷机故障）/ 长安服务区（维修供电）',
     '#1565C0', '#E3F2FD', 'png'),
    ('track_stop_point', '关键节点-1：冷机停机点',
     '位置：沪昆高速 嘉兴段 K128+450  东向西方向\n时间：23:10:23    冷机故障码 P0216（燃油喷射正时）\n环境温度 26C  车厢温度 -20.7C（持续上升中）',
     '#B71C1C', '#FFEBEE', 'png'),
    ('photo_cooler_dashboard', '冷机故障仪表盘实拍',
     '冷机控制器：CARRIER Supra 850  序列号 CR850-SH23071\n故障码：P0216 燃油喷射正时电路故障\n发动机转速：0 RPM    排气温度：--    电池电压：12.4V',
     '#E65100', '#FFF3E0', 'jpg'),
    ('photo_temp_recorder', '车厢温度记录仪截图',
     '双温区记录仪：ELITECH RCW-800WiFi  共12个测点\n主货厢平均温度 -15.4C  [已越线，阈值 -18.0C]\n记录间隔 1min  内存已存 32740 条  电池余量 87%',
     '#4527A0', '#EDE7F6', 'jpg'),
    ('photo_arrival_inspection', '到货抽检外观照片',
     '托盘编号 1-12    抽检比例 20%\n外包装完好率 100%  无凝露 无软化 无破损\n温度探针抽检：-20.1C  -19.8C  -20.5C',
     '#1B5E20', '#E8F5E9', 'jpg'),
]

for k, t, s, ct, cb, ext in existing:
    fn = '{}_{}_{}_{}.{}'.format(rec, k, plate, date_str, ext)
    path = os.path.join(out_dir, fn)
    make_img(path, t, s, ct, cb)
    print('OK 生成:', fn)

print()
print('缺失项（故意不生成，用于演示缺失提示）:')
print('  - track_repair_point 长安服务区维修供电点轨迹截图')
print('  - photo_repair_generator 维修现场外接发电机照片')
print()
print('保存目录:', out_dir)
print()
print('注：实际使用时，上述图片请替换为车队或司机提供的原始照片/截图。')
