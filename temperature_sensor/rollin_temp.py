from temperature_sensor import *

import time

if __name__ == "__main__":
    sensor = MLX90614()
    
    try:
        while True:
            print("Object:", sensor.readObjectTemperature())
            print("Ambient:", sensor.readAmbientTemperature())
            print("---")
            time.sleep(2)  # wait 20 seconds
    except KeyboardInterrupt:
        print("Stopped by user")

