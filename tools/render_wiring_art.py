"""Deterministic, editable SVG wiring diagrams for the current GP29 prototype.

Logical net diagrams, not a guessed physical header/PCB layout. Labels and
GPIO assignments are shared with docs/PINOUT.md and validated separately.
"""
from pathlib import Path
from html import escape

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'docs/assets'
OUT.mkdir(exist_ok=True)
INK, MUTED, RED, TEAL, BLUE = '#202a35','#56636f','#c63353','#257e7c','#2563a1'

def start(w,h,title,subtitle):
    return [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" role="img" aria-label="{escape(title)}">',
            f'<title>{escape(title)}</title>',
            '<style>text{font-family:Arial,DejaVu Sans,sans-serif;fill:#202a35} .small{font-size:21px;fill:#56636f} .label{font-size:24px} .head{font-size:28px;font-weight:700} .wire{fill:none;stroke-width:4;stroke-linecap:round;stroke-linejoin:round}</style>',
            f'<rect width="{w}" height="{h}" fill="#f7f7f2"/>',
            f'<text x="55" y="64" font-size="36" font-weight="700">{escape(title)}</text>',
            f'<text x="55" y="107" class="small">{escape(subtitle)}</text>']

def text(s,x,y,label,cls='label',color=None):
    s.append(f'<text x="{x}" y="{y}" class="{cls}"'+(f' style="fill:{color}"' if color else '')+f'>{escape(label)}</text>')

def card(s,x,y,w,h,title):
    s.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="18" fill="#fff" stroke="#d6dcd9" stroke-width="2"/>')
    text(s,x+24,y+43,title,'head')

def line(s,pts,color=INK):
    s.append(f'<polyline points="'+ ' '.join(f'{x},{y}' for x,y in pts)+f'" class="wire" stroke="{color}"/>')

def dot(s,x,y,color):
    s.append(f'<circle cx="{x}" cy="{y}" r="6" fill="{color}"/>')

def save(s,name):
    (OUT/name).write_text('\n'.join(s+['</svg>'])+'\n')

s=start(1600,1130,'ScarletPico · сигналы RP2040-Zero',
        'GPIO-номера, не номера ножек. Логическая схема: положение контактов на плате не показано.')
card(s,60,160,480,440,'TFT ST7796 + microSD · SPI0')
spi=[(6,'SCK / CLK → TFT и microSD'),(7,'MOSI / SDI / DI → оба модуля'),
     (4,'MISO / DO ← microSD'),(5,'TFT · CS'),(8,'TFT · DC / RS'),
     (9,'TFT · RESET / RST'),(10,'TFT · BL / LED, управление'),(3,'microSD · CS')]
card(s,720,160,250,790,'RP2040-Zero')
text(s,747,237,'Логика 3,3 В','small')
for i,(pin,label) in enumerate(spi):
    y=285+i*39
    text(s,84,y+7,label,'small')
    line(s,[(540,y),(720,y)],TEAL)
    dot(s,720,y,TEAL);text(s,741,y+7,f'GP{pin}')
text(s,84,635,'TFT SDO/MISO — только если это','small')
text(s,84,667,'проверенный 3-state выход 3,3 В.','small')
card(s,60,705,480,220,'MAX98357A · I2S')
for i,(pin,label) in enumerate([(11,'BCLK'),(12,'LRC / LRCLK / WS'),(13,'DIN')]):
    y=785+i*43
    text(s,84,y+7,label)
    line(s,[(540,y),(720,y)],BLUE);dot(s,720,y,BLUE)
    text(s,741,y+7,f'GP{pin}')
card(s,1130,160,410,470,'Кнопки · замыкание на GND')
for i,(pin,label) in enumerate([(0,'Вверх'),(1,'Вниз'),(2,'Влево'),(14,'Вправо'),
                                (15,'A'),(26,'B'),(27,'Start'),(28,'Select')]):
    y=275+i*43
    line(s,[(970,y),(1130,y)],RED);dot(s,970,y,RED)
    text(s,985,y-10,f'GP{pin}','small',RED)
    text(s,1154,y+8,label)
text(s,1154,661,'Внутренние pull-up; нажато = LOW.','small')
card(s,1130,720,410,205,'Аккумулятор · ADC3')
line(s,[(970,806),(1130,806)],BLUE);dot(s,970,806,BLUE)
text(s,985,790,'GP29','small',BLUE)
text(s,1154,807,'Выход делителя 4,7k / 4,7k')
text(s,1154,851,'4,20 В → около 2,10 В','small')
text(s,1154,890,'Не 5V и не контакт 3V3.','small',RED)
text(s,55,1005,'Питание — отдельная схема. Общая земля сигналов: защищённый OUT− TP4056.','label')
text(s,55,1048,'3V3 RP2040-Zero → VCC экрана и microSD. Обвязка BL/IM зависит от конкретного TFT-модуля.','small')
text(s,55,1085,'GP16–25 не требуются. GP26–28 заняты кнопками. Зарядные CHRG/STDBY к MCU не подключены.','small')
save(s,'wiring-signals.svg')

s=start(1800,1080,'ScarletPico · питание и измерение батареи',
        'Одноэлементный Li-ion/LiPo 4,2 В · TP4056 с защитой · повышайка с общим минусом')
card(s,55,175,270,170,'USB-C · зарядка')
text(s,80,255,'VBUS / +5V',color=RED)
text(s,80,306,'GND')
card(s,450,175,330,235,'TP4056 + защита')
text(s,470,255,'IN+',color=RED);text(s,470,306,'IN−')
text(s,680,255,'OUT+',color=RED);text(s,680,355,'OUT−')
text(s,520,388,'B+');text(s,635,388,'B−')
line(s,[(325,247),(450,247)],RED)
line(s,[(325,298),(450,298)])
card(s,450,520,330,135,'Аккумулятор · 1S')
text(s,475,613,'+ / − только к B+ / B−','small')
line(s,[(550,410),(550,520)],RED)
line(s,[(650,410),(650,520)])
text(s,820,183,'SW1 · выключатель','small')
line(s,[(780,247),(850,247)],RED)
dot(s,850,247,RED);dot(s,980,247,RED)
line(s,[(850,247),(961,210)],RED)
line(s,[(980,247),(1110,247)],RED)
card(s,1110,175,270,235,'Повышайка')
text(s,1130,258,'IN+',color=RED);text(s,1130,355,'IN−')
text(s,1250,258,'OUT+ 5V',color=RED);text(s,1250,355,'OUT−')
text(s,1130,395,'Общий IN− / OUT−','small')
card(s,1490,175,255,265,'RP2040-Zero')
text(s,1510,258,'5V',color=RED);text(s,1510,355,'GND')
text(s,1570,411,'GP29 / ADC3','small',BLUE)
line(s,[(1380,247),(1490,247)],RED)
line(s,[(780,347),(850,347),(850,820),(1640,820)])
line(s,[(850,347),(1110,347)])
line(s,[(1380,347),(1450,347),(1490,347)])
line(s,[(1450,347),(1450,820)])
dot(s,1450,820,INK)
text(s,60,740,'Защита аккумулятора не должна','small')
text(s,60,778,'обходиться общей перемычкой.','small')
text(s,60,830,'B− / IN− ≠ системный OUT−','label',RED)
# Sense source comes from the switched battery rail, never the 5V output.
dot(s,1040,247,RED)
s.append('<circle cx="1040" cy="347" r="9" fill="#f7f7f2"/>')
line(s,[(1040,247),(1040,480)],RED)
s.append(f'<rect x="1018" y="480" width="44" height="100" fill="#fff" stroke="{BLUE}" stroke-width="4"/>')
text(s,865,498,'R1 · 4,7 кОм','small',BLUE)
text(s,900,536,'472','small')
line(s,[(1040,580),(1040,650)],BLUE)
dot(s,1040,650,BLUE)
s.append('<circle cx="1450" cy="650" r="9" fill="#f7f7f2"/>')
line(s,[(1040,650),(1640,650),(1640,440)],BLUE)
text(s,1120,610,'Общая точка → GP29','label',BLUE)
line(s,[(1040,650),(1040,680)],BLUE)
s.append(f'<rect x="1018" y="680" width="44" height="100" fill="#fff" stroke="{BLUE}" stroke-width="4"/>')
text(s,865,720,'R2 · 4,7 кОм','small',BLUE)
text(s,900,758,'472','small')
line(s,[(1040,780),(1040,820)])
dot(s,1040,820,INK)
line(s,[(1230,650),(1230,700)],BLUE)
dot(s,1230,650,BLUE)
line(s,[(1195,700),(1265,700)],BLUE)
line(s,[(1195,723),(1265,723)],BLUE)
line(s,[(1230,723),(1230,820)])
dot(s,1230,820,INK)
text(s,1275,705,'C1 · керамика','small')
text(s,1275,747,'100 нФ…1 мкФ','small')
text(s,1275,785,'без полярности','small')
text(s,1030,865,'OUT− / общий GND системы','small')
text(s,55,940,'R1 берёт плюс ПОСЛЕ выключателя, ДО повышайки. При 4,20 В на входе: GP29 ≈ 2,10 В.','label',BLUE)
text(s,55,987,'Сначала проверить делитель мультиметром без GP29. Пайка — только с отключёнными аккумулятором и USB.','small')
text(s,55,1026,'Нет проверенного power-path для одновременного USB и батареи. Номинал C1 с донора не подтверждён.','small')
save(s,'wiring-power.svg')
print('Wrote docs/assets/wiring-signals.svg and wiring-power.svg')
