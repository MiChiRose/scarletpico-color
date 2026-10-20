"""Deterministic wiring drawing for the two-472 battery voltage divider."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent / 'divider-472-wiring.png'
im = Image.new('RGB', (1600, 1170), 'white')
d = ImageDraw.Draw(im)
FONT = '/System/Library/Fonts/Supplemental/Arial.ttf'
BOLD = '/System/Library/Fonts/Supplemental/Arial Bold.ttf'
ink, muted = '#17212b', '#4b5563'
red, blue, ground = '#b52b25', '#1262ac', '#25313b'

def text(x, y, s, size=27, fill=ink, bold=False, anchor=None):
    d.text((x,y),s,font=ImageFont.truetype(BOLD if bold else FONT,size),fill=fill,anchor=anchor)

def wire(points, color):
    d.line(points, fill=color, width=8, joint='curve')

def node(x,y,color):
    d.ellipse((x-11,y-11,x+11,y+11),fill=color)

def terminal(x,y,color):
    d.ellipse((x-15,y-15,x+15,y+15),fill='white',outline=color,width=6)

def resistor(y):
    # Physical SMD body, end terminations and the actual marking.
    d.rounded_rectangle((458,y,542,y+120),radius=6,fill='#23262a')
    d.rectangle((458,y,542,y+17),fill='#b7bec5')
    d.rectangle((458,y+103,542,y+120),fill='#b7bec5')
    text(500,y+60,'472',29,'white',True,'mm')

text(60,40,'Измерение аккумулятора · RP2040-Zero',44,bold=True)
text(60,104,'Два резистора 472 = 4,7 кОм каждый. Только измерение, не питание платы.',27,muted)

text(65,170,'1. ПЛЮС ПОСЛЕ ВЫКЛЮЧАТЕЛЯ',29,red,True)
text(65,211,'Та же точка, что идёт на IN+ повышайки',25,muted)
wire([(100,270),(500,270),(500,300)],red)
terminal(100,270,red)
resistor(300)
text(570,325,'R1 — 4,7 кОм',30,bold=True)
text(570,369,'Маркировка 472; полярности нет',25,muted)
wire([(500,420),(500,510)],blue)

# One common signal node: R1 bottom, R2 top, capacitor top and ADC output.
wire([(500,510),(500,650)],blue)
wire([(500,510),(1280,510)],blue)
wire([(900,510),(900,690)],blue)
node(500,510,blue)
node(900,510,blue)
terminal(1280,510,blue)
text(1050,412,'2. ВЫХОД НА GP29',30,blue,True)
text(1050,455,'Контакт «29», НЕ «3V3»',26,muted)
text(530,540,'Общая точка пайки',25,blue)

resistor(650)
text(570,674,'R2 — 4,7 кОм',30,bold=True)
text(570,716,'Тоже 472',25,muted)
wire([(500,770),(500,900)],ground)

# Non-polar ceramic capacitor, connected in parallel with R2.
d.line([(850,690),(950,690)],fill=ink,width=8)
d.line([(850,725),(950,725)],fill=ink,width=8)
wire([(900,725),(900,900)],ground)
text(990,655,'C1 — керамический',29,bold=True)
text(990,700,'100 нФ – 1 мкФ',28)
text(990,741,'Полярности нет',25,muted)

wire([(500,900),(1280,900)],ground)
node(900,900,ground)
terminal(1280,900,ground)
text(1030,815,'3. ОБЩАЯ ЗЕМЛЯ',30,ground,True)
text(1030,857,'OUT− TP4056 / GND RP2040',25,muted)

text(65,605,'Проверка мультиметром',28,bold=True)
text(65,651,'Чёрный щуп → точка 3',25)
text(65,692,'Красный щуп → точка 2',25)
text(65,748,'Напряжение здесь — половина',24,muted)
text(65,783,'напряжения аккумулятора.',24,muted)
text(65,829,'4,20 В → примерно 2,10 В',25,blue,True)

d.line([(60,960),(1540,960)],fill='#cbd0d5',width=2)
text(60,982,'Схема рассчитана на повышайку с общим минусом IN− и OUT−.',26,bold=True)
text(60,1026,'Пайка: аккумулятор и USB отключены. B− и OUT− TP4056 не соединять перемычкой.',25)
text(60,1067,'Сначала проверить делитель без подключения к GP29. Затем обесточить и подключить GP29.',25)
text(60,1108,'C1: номинал детали с донора пока не подтверждён. Электролиты 22/100 мкФ здесь не показаны.',24,muted)

im.save(OUT)
print(OUT)
