import smbus
import time
import math
import numpy as np

# MPU6050 registers
MPU_ADDR = 0x68
ACCEL_XOUT = 0x3B
PWR_MGMT_1 = 0x6B

bus = smbus.SMBus(1)

# Wake up MPU6050
bus.write_byte_data(MPU_ADDR, PWR_MGMT_1, 0)

def read_word(reg):
    high = bus.read_byte_data(MPU_ADDR, reg)
    low = bus.read_byte_data(MPU_ADDR, reg + 1)
    val = (high << 8) + low
    return val - 65536 if val > 32768 else val

def read_accel():
    ax = read_word(ACCEL_XOUT) / 16384.0
    ay = read_word(ACCEL_XOUT + 2) / 16384.0
    az = read_word(ACCEL_XOUT + 4) / 16384.0
    return ax, ay, az

# Parameters
WALK_THRESHOLD = 0.15  # g
WINDOW_SIZE = 10
accel_buffer = []

print("Monitoring motion...")

while True:
    ax, ay, az = read_accel()

    # Remove gravity (rough)
    accel_mag = math.sqrt(ax**2 + ay**2 + az**2)
    linear_accel = abs(accel_mag - 1.0)

    accel_buffer.append(linear_accel)
    if len(accel_buffer) > WINDOW_SIZE:
        accel_buffer.pop(0)

    avg_accel = np.mean(accel_buffer)

    if avg_accel > WALK_THRESHOLD:
        print("Walking detected | Avg Accel:", round(avg_accel, 3))
    else:
        print("Still")

    time.sleep(0.05)  # 20 H