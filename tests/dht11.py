#!/usr/bin/env python3
"""
DHT11 Test Script (GPIO, single sensor)

- Uses a DHT11 on Raspberry Pi GPIO6 (BCM, physical pin 31)
- Reads several samples per block and computes an average
- Runs for a limited number of blocks, then exits
- Prints clear status and error messages in English
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

# DHT11 wiring:
# - Data: GPIO6 (BCM), physical pin 31
# - VCC : 3.3V
# - GND : any GND pin
GPIO = board.D6

SAMPLE_INTERVAL = 2          # seconds between single reads
SAMPLES_PER_BLOCK = 5         # readings per average block
MAX_BLOCKS = 3                # number of average blocks before exit


def init_sensor():
    """Create DHT11 sensor object and handle possible errors."""
    try:
        sensor = adafruit_dht.DHT11(GPIO, use_pulseio=False)
        return sensor
    except Exception as e:
        print("[ERROR] Could not initialize DHT11 sensor on GPIO6 (BCM).")
        print("        Please check wiring and permissions.")
        print(f"        Details: {e}")
        sys.exit(1)


def read_dht11(sensor, retries=10, delay=0.3):
    """
    Read DHT11 multiple times and return median values.

    Returns:
        (temperature_c, humidity_percent) or (None, None) if no valid values.
    """
    temps = []
    hums = []

    for _ in range(retries):
        try:
            t = sensor.temperature
            h = sensor.humidity
            if (
                t is not None
                and h is not None
                and -20.0 <= t <= 60.0
                and 0.0 <= h <= 100.0
            ):
                temps.append(float(t))
                hums.append(float(h))
        except RuntimeError:
            # DHT11 is noisy; ignore single read errors
            pass
        except Exception as e:
            print(f"[WARNING] Unexpected read error: {e}")
            break

        time.sleep(delay)

    if temps and hums:
        return statistics.median(temps), statistics.median(hums)
    return None, None


def main():
    print("=== DHT11 Test (GPIO interface) ===")
    print("Sensor:      DHT11")
    print("Interface:   GPIO (digital), BCM pin 6, physical pin 31")
    print("Power:       3.3V and GND")
    print(f"Samples:     {SAMPLES_PER_BLOCK} values per block")
    print(f"Interval:    {SAMPLE_INTERVAL} seconds between reads")
    print(f"Max blocks:  {MAX_BLOCKS}")
    print()

    sensor = init_sensor()

    # Small delay to let the sensor stabilize
    time.sleep(2.0)

    temp_values = []
    hum_values = []
    completed_blocks = 0

    print("Starting measurements...")
    print()

    try:
        while completed_blocks < MAX_BLOCKS:
            t, h = read_dht11(sensor)

            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

            if t is not None:
                temp_values.append(t)
                hum_values.append(h)
                print(
                    f"{timestamp}  Single: {t:5.1f} C  {h:5.1f} %  "
                    f"({len(temp_values)}/{SAMPLES_PER_BLOCK})"
                )
            else:
                print(f"{timestamp}  No valid DHT11 values in this cycle")

            if len(temp_values) >= SAMPLES_PER_BLOCK:
                avg_temp = statistics.mean(temp_values)
                avg_hum = statistics.mean(hum_values)

                print("--------------------------------------------------")
                print(
                    f"{timestamp}  Average of {SAMPLES_PER_BLOCK} samples:"
                )
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
        print("\n[INFO] Interrupted by user. Stopping DHT11 test.")

    except Exception as e:
        print(f"[ERROR] Unexpected error in main loop: {e}")

    finally:
        # Clean up sensor object
        try:
            sensor.exit()
        except Exception:
            pass
        print("[INFO] DHT11 test finished.")
        print("=== Test complete ===")


if __name__ == "__main__":
    main()
