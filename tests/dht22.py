#!/usr/bin/env python3
"""
DHT22 Test Script (GPIO, AM2302 sensor)

- Uses a DHT22 (AM2302) on Raspberry Pi GPIO6 (BCM, physical pin 31)
- Reads multiple samples and calculates medians and block averages
- Runs only a limited number of blocks, then exits
- Prints clear status messages and error hints
"""

import time
import statistics
import sys

# Try to import required libraries
try:
    import board
except ImportError:
    print("[ERROR] Python module 'board' (Adafruit Blinka) is not installed.")
    print("        Install with:")
    print("        sudo pip3 install adafruit-blinka")
    sys.exit(1)

try:
    import adafruit_dht
except ImportError:
    print("[ERROR] Python module 'adafruit_dht' is not installed.")
    print("        Install with:")
    print("        sudo pip3 install adafruit-circuitpython-dht")
    print("        On Raspberry Pi you may also need:")
    print("        sudo apt-get install libgpiod2")
    sys.exit(1)


# DHT22 wiring:
# - Data: GPIO6 (BCM), physical pin 31
# - VCC : 3.3V
# - GND : any GND pin
GPIO = board.D6

SAMPLE_INTERVAL = 10        # seconds between reads
SAMPLES_PER_BLOCK = 5       # readings per average block
MAX_BLOCKS = 3              # number of average blocks before exit


def init_sensor():
    """Initialize the DHT22 sensor and handle errors."""
    try:
        sensor = adafruit_dht.DHT22(GPIO, use_pulseio=False)
        return sensor
    except Exception as e:
        print("[ERROR] Could not initialize DHT22 sensor on GPIO6 (BCM).")
        print("        Please check wiring and permissions.")
        print(f"        Details: {e}")
        sys.exit(1)


def read_dht22(sensor, retries=10, delay=0.3):
    """
    Read DHT22 sensor multiple times and return median values.

    Returns:
        (temperature_c, humidity_percent) or (None, None)
    """
    temps = []
    hums = []

    for _ in range(retries):
        try:
            t = sensor.temperature
            h = sensor.humidity
            if (
                t is not None and h is not None and
                -40.0 <= t <= 80.0 and
                0.0  <= h <= 100.0
            ):
                temps.append(float(t))
                hums.append(float(h))
        except RuntimeError:
            # DHT22 occasionally gives read errors; ignore them
            pass
        except Exception as e:
            print(f"[WARNING] Unexpected read error: {e}")
            break

        time.sleep(delay)

    if temps and hums:
        return statistics.median(temps), statistics.median(hums)
    return None, None


def main():
    print("=== DHT22 Test (GPIO interface) ===")
    print("Sensor:      DHT22 (AM2302)")
    print("Interface:   GPIO (digital), BCM pin 6, physical pin 31")
    print("Power:       3.3V and GND")
    print(f"Samples:     {SAMPLES_PER_BLOCK} values per block")
    print(f"Interval:    {SAMPLE_INTERVAL} seconds between reads")
    print(f"Max blocks:  {MAX_BLOCKS}")
    print()

    sensor = init_sensor()

    # Allow sensor to stabilize
    time.sleep(2.0)

    temp_values = []
    hum_values = []
    completed_blocks = 0

    print("Starting measurements...")
    print()

    try:
        while completed_blocks < MAX_BLOCKS:
            t, h = read_dht22(sensor)

            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

            if t is not None:
                temp_values.append(t)
                hum_values.append(h)
                print(
                    f"{timestamp}  Single: {t:5.1f} C  {h:5.1f} %  "
                    f"({len(temp_values)}/{SAMPLES_PER_BLOCK})"
                )
            else:
                print(f"{timestamp}  No valid DHT22 values in this cycle")

            # When enough samples collected -> compute block average
            if len(temp_values) >= SAMPLES_PER_BLOCK:
                avg_temp = statistics.mean(temp_values)
                avg_hum = statistics.mean(hum_values)

                print("--------------------------------------------------")
                print(f"{timestamp}  Average of {SAMPLES_PER_BLOCK} samples:")
                print(f"Temperature: {avg_temp:6.2f} C")
                print(f"Humidity   : {avg_hum:6.2f} %")
                print("--------------------------------------------------")
                print()

                temp_values.clear()
                hum_values.clear()
                completed_blocks += 1

            if completed_blocks >= MAX_BLOCKS:
                break

            time.sleep(SAMPLE_INTERVAL)

    except KeyboardInterrupt:
        print("\n[INFO] Interrupted by user. Stopping DHT22 test.")

    except Exception as e:
        print(f"[ERROR] Unexpected error in main loop: {e}")

    finally:
        try:
            sensor.exit()
        except Exception:
            pass
        print("[INFO] DHT22 test finished.")
        print("=== Test complete ===")


if __name__ == "__main__":
    main()
