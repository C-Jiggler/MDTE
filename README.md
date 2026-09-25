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

# --- 1. NeoPixel Setup (GP10) ---
NUM_LEDS = 64
pixels = neopixel.NeoPixel(
    board.GP10,
    NUM_LEDS,
    brightness=0.3,
    auto_write=False,
    pixel_order=neopixel.GRB,
)
pixels.fill((0, 0, 0))
pixels.show()

# Sand & Hourglass Colors & Buffer
# BG_COLOR is now a very faint, warm amber/dim sand tone
BG_COLOR = (15, 10, 2)

# DRIP_PALETTE is now a mix of bright sand, warm gold, and light beige
DRIP_PALETTE = [
    (255, 200, 100),    # Bright Sand / Golden Yellow
    (240, 170, 70),     # Warm Amber
    (255, 225, 160),    # Light Beige / Highlight Sand
    (220, 150, 50),     # Deep Sand Grain
    (255, 240, 200),    # Soft Off-White Sand Sparkle
]

# We use an 8x8 2D grid
grid_buffer = [[list(BG_COLOR) for _ in range(8)] for _ in range(8)]

def get_zigzag_index(x, y):
    """Translates 2D (x, y) coordinates into the 1D zig-zag wire path."""
    if y % 2 == 0:
        return (y * 8) + x        # Even rows go left to right
    else:
        return (y * 8) + (7 - x)  # Odd rows go right to left

def step_waterfall():
    """Calculates one frame of the sand falling animation on an 8x8 grid."""
    # 1. Fade all existing pixels back to the dim sand background
    for y in range(8):
        for x in range(8):
            for c in range(3):
                if grid_buffer[y][x][c] > BG_COLOR[c]:
                    grid_buffer[y][x][c] = max(
                        BG_COLOR[c], int(grid_buffer[y][x][c] * 0.70)
                    )

    # 2. Shift everything down one row (from bottom to top)
    for y in range(7, 0, -1):
        for x in range(8):
            grid_buffer[y][x] = list(grid_buffer[y - 1][x])

    # 3. Generate new random sand grains at the very top row (y = 0)
    for x in range(8):
        if random.random() < 0.15:
            grid_buffer[0][x] = list(random.choice(DRIP_PALETTE))
        else:
            grid_buffer[0][x] = list(BG_COLOR)

    # 4. Map the 2D grid to the physical NeoPixel zig-zag strip
    for y in range(8):
        for x in range(8):
            idx = get_zigzag_index(x, y)
            pixels[idx] = tuple(grid_buffer[y][x])

    pixels.show()

# --- 2. OLED Screen Setup (SH1106) ---
i2c = busio.I2C(scl=board.GP1, sda=board.GP0)

try:
    import i2cdisplaybus
    display_bus = i2cdisplaybus.I2CDisplayBus(
        i2c, device_address=0x3C
    )
except ImportError:
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

WATERFALL_INTERVAL = 120

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

    # 3. Handle Timer & Non-Blocking Sand Fall
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

                # Alarm Flash (Using a warm orange flash for the theme)
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
