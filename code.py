import random
import time
import board
import busio
import digitalio
import neopixel
import displayio
import terminalio
from adafruit_display_text import label
import adafruit_displayio_sh1106
from adafruit_ticks import ticks_ms, ticks_diff

# Release displays to avoid pin lockouts
displayio.release_displays()

# --- 1. NeoPixel Setup (GP15) ---
NUM_LEDS = 8
pixels = neopixel.NeoPixel(
    board.GP15,
    NUM_LEDS,
    brightness=0.3,
    auto_write=False,
    pixel_order=neopixel.GRB,
)
pixels.fill((0, 0, 0))
pixels.show()

# Waterfall Colors & Buffer
BG_COLOR = (0, 2, 15)
DRIP_PALETTE = [
    (0, 220, 255),    # Vibrant Cyan
    (0, 255, 150),    # Sea Green
    (180, 230, 255),  # Foamy White
    (0, 100, 255),    # Water Blue
    (150, 50, 255),   # Violet Wave
]

pixel_buffer = [list(BG_COLOR) for _ in range(NUM_LEDS)]


def fade_to_background(buffer, bg, decay_rate=0.70):
    """Slowly fades pixels back toward background color."""
    for i in range(len(buffer)):
        for c in range(3):
            if buffer[i][c] > bg[c]:
                buffer[i][c] = max(
                    bg[c], int(buffer[i][c] * decay_rate)
                )


def step_waterfall():
    """Calculates one frame of the waterfall animation."""
    fade_to_background(pixel_buffer, BG_COLOR, decay_rate=0.70)

    for i in range(NUM_LEDS - 1, 0, -1):
        pixel_buffer[i] = list(pixel_buffer[i - 1])

    if random.random() < 0.35:
        pixel_buffer[0] = list(random.choice(DRIP_PALETTE))
    else:
        pixel_buffer[0] = list(BG_COLOR)

    for i in range(NUM_LEDS):
        pixels[i] = tuple(pixel_buffer[i])
    pixels.show()


# --- 2. OLED Screen Setup (SH1106) ---
i2c = busio.I2C(scl=board.GP1, sda=board.GP0)

try:
    import i2cdisplaybus
    display_bus = i2cdisplaybus.I2CDisplayBus(
        i2c, device_address=0x3C
    )
except AttributeError:
    display_bus = displayio.I2CDisplay(
        i2c, device_address=0x3C
    )

WIDTH = 128
HEIGHT = 64
display = adafruit_displayio_sh1106.SH1106(
    display_bus, width=WIDTH, height=HEIGHT
)

# Setup Display Group
main_group = displayio.Group()
display.root_group = main_group

line1_label = label.Label(
    terminalio.FONT,
    text="Set Time: 60s",
    color=0xFFFFFF,
    x=0,
    y=10,
)
line2_label = label.Label(
    terminalio.FONT,
    text="Press PSH to Start",
    color=0xFFFFFF,
    x=0,
    y=35,
)
main_group.append(line1_label)
main_group.append(line2_label)

# --- 3. Digital Inputs (Encoder & Buttons) ---
tra = digitalio.DigitalInOut(board.GP3)
trb = digitalio.DigitalInOut(board.GP4)
psh = digitalio.DigitalInOut(board.GP5)
con_btn = digitalio.DigitalInOut(board.GP6)
bak_btn = digitalio.DigitalInOut(board.GP7)

for pin in (tra, trb, psh, con_btn, bak_btn):
    pin.direction = digitalio.Direction.INPUT
    pin.pull = digitalio.Pull.UP

# --- State Variables ---
timer_seconds = 60
time_remaining = 60
timer_active = False

last_tra_state = tra.value
last_second_tick = ticks_ms()
last_waterfall_tick = ticks_ms()

WATERFALL_INTERVAL = 40  # 40ms updates (~25 FPS)

# --- Main Program Loop ---
while True:
    current_time = ticks_ms()

    # 1. Read Rotary Encoder
    current_tra_state = tra.value
    if current_tra_state != last_tra_state and not timer_active:
        if trb.value != current_tra_state:
            timer_seconds += 5
        else:
            timer_seconds = max(5, timer_seconds - 5)
        time_remaining = timer_seconds

        line1_label.text = f"Set Time: {timer_seconds}s"
        line2_label.text = "Press PSH to Start"
    last_tra_state = current_tra_state

    # 2. Read Dial Button (Start / Pause)
    if not psh.value:
        timer_active = not timer_active
        time.sleep(0.2)  # Debounce

        if timer_active:
            line1_label.text = "Timer Running!"
            line2_label.text = f"Remaining: {time_remaining}s"
        else:
            line1_label.text = "Timer Paused"
            pixels.fill((0, 0, 0))
            pixels.show()

    # 3. Handle Timer & Non-Blocking Waterfall
    if timer_active:
        if ticks_diff(current_time, last_waterfall_tick) >= WATERFALL_INTERVAL:
            step_waterfall()
            last_waterfall_tick = current_time

        if ticks_diff(current_time, last_second_tick) >= 1000:
            time_remaining -= 1
            last_second_tick = current_time
            line1_label.text = f"Remaining: {time_remaining}s"

            if time_remaining <= 0:
                timer_active = False
                line1_label.text = "TIME'S UP!"
                line2_label.text = ""

                # Alarm Flash
                for _ in range(3):
                    pixels.fill((255, 0, 0))
                    pixels.show()
                    time.sleep(0.2)
                    pixels.fill((0, 0, 0))
                    pixels.show()
                    time.sleep(0.2)

                time_remaining = timer_seconds
                line1_label.text = f"Set Time: {timer_seconds}s"
                line2_label.text = "Press PSH to Start"

    # 4. Extra Buttons Handling (Reset)
    if not bak_btn.value or not con_btn.value:
        timer_active = False
        time_remaining = timer_seconds
        pixels.fill((0, 0, 0))
        pixels.show()
        line1_label.text = f"Reset: {timer_seconds}s"
        line2_label.text = "Press PSH to Start"
        time.sleep(0.2)

    time.sleep(0.001)
