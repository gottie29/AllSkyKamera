#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
DHT22 Test Script for one or two sensors on Raspberry Pi GPIO pins

Features:
- Test one or two DHT22 / AM2302 sensors
- GPIO pins can be passed via command line
- Can test sensor1, sensor2, or both
- Reads multiple retries per cycle and uses median values
- Builds average blocks from valid samples
- Clear status output and helpful error messages

Examples:
  python3 dht_test.py
  python3 dht_test.py --gpio1 5
  python3 dht_test.py --gpio1 5 --gpio2 6 --mode both
  python3 dht_test.py --gpio1 5 --gpio2 6 --mode sensor1
  python3 dht_test.py --gpio1 5 --gpio2 6 --mode sensor2
  python3 dht_test.py --gpio1 17 --samples-per-block 3 --max-blocks 2 --interval 5
"""

import time
import statistics
import sys
import argparse

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


DEFAULT_GPIO1 = 5
DEFAULT_GPIO2 = 6
DEFAULT_SAMPLE_INTERVAL = 10
DEFAULT_SAMPLES_PER_BLOCK = 5
DEFAULT_MAX_BLOCKS = 3


def parse_args():
    parser = argparse.ArgumentParser(
        description="Test one or two DHT22 sensors on Raspberry Pi GPIO pins."
    )
    parser.add_argument(
        "--gpio1",
        type=int,
        default=DEFAULT_GPIO1,
        help="BCM GPIO pin for sensor 1 (default: %(default)s)"
    )
    parser.add_argument(
        "--gpio2",
        type=int,
        default=DEFAULT_GPIO2,
        help="BCM GPIO pin for sensor 2 (default: %(default)s)"
    )
    parser.add_argument(
        "--mode",
        choices=["sensor1", "sensor2", "both"],
        default="both",
        help="Which sensor(s) to test (default: %(default)s)"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=DEFAULT_SAMPLE_INTERVAL,
        help="Seconds between reads (default: %(default)s)"
    )
    parser.add_argument(
        "--samples-per-block",
        type=int,
        default=DEFAULT_SAMPLES_PER_BLOCK,
        help="Valid samples per average block (default: %(default)s)"
    )
    parser.add_argument(
        "--max-blocks",
        type=int,
        default=DEFAULT_MAX_BLOCKS,
        help="Number of average blocks before exit (default: %(default)s)"
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=10,
        help="Read retries per measurement cycle (default: %(default)s)"
    )
    parser.add_argument(
        "--retry-delay",
        type=float,
        default=0.3,
        help="Delay in seconds between retries (default: %(default)s)"
    )
    return parser.parse_args()


def bcm_to_board_pin(gpio_number):
    """
    Convert BCM GPIO number to board.<Dxx> pin object.
    Example: 5 -> board.D5
    """
    attr_name = "D{0}".format(gpio_number)
    try:
        return getattr(board, attr_name)
    except AttributeError:
        print("[ERROR] GPIO{0} (BCM) is not available as board.{1}".format(gpio_number, attr_name))
        print("        Please choose a valid BCM GPIO pin.")
        sys.exit(1)


def init_sensor(gpio_number, label):
    """Initialize one DHT22 sensor and handle errors."""
    board_pin = bcm_to_board_pin(gpio_number)
    try:
        sensor = adafruit_dht.DHT22(board_pin, use_pulseio=False)
        return sensor
    except Exception as e:
        print("[ERROR] Could not initialize {0} on GPIO{1} (BCM).".format(label, gpio_number))
        print("        Please check wiring, power, pull-up resistor, and permissions.")
        print("        Details: {0}".format(e))
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
                0.0 <= h <= 100.0
            ):
                temps.append(float(t))
                hums.append(float(h))

        except RuntimeError:
            # DHT22 occasionally gives read errors; ignore them
            pass
        except Exception as e:
            print("[WARNING] Unexpected read error: {0}".format(e))
            break

        time.sleep(delay)

    if temps and hums:
        return statistics.median(temps), statistics.median(hums)

    return None, None


def print_header(args, active_sensors):
    print("=== DHT22 Test (GPIO interface) ===")
    print("Sensor type:        DHT22 / AM2302")
    print("Mode:               {0}".format(args.mode))
    for label, gpio_number in active_sensors:
        print("{0}:            GPIO{1} (BCM)".format(label, gpio_number))
    print("Samples per block:  {0}".format(args.samples_per_block))
    print("Interval:           {0} seconds".format(args.interval))
    print("Max blocks:         {0}".format(args.max_blocks))
    print("Retries per read:   {0}".format(args.retries))
    print("Retry delay:        {0} seconds".format(args.retry_delay))
    print()


def create_sensor_state():
    return {
        "temp_values": [],
        "hum_values": [],
        "completed_blocks": 0,
    }


def handle_measurement(label, sensor, state, args):
    t, h = read_dht22(sensor, retries=args.retries, delay=args.retry_delay)
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

    if t is not None:
        state["temp_values"].append(t)
        state["hum_values"].append(h)
        print(
            "{0}  {1}: Single: {2:5.1f} C  {3:5.1f} %  ({4}/{5})".format(
                timestamp,
                label,
                t,
                h,
                len(state["temp_values"]),
                args.samples_per_block
            )
        )
    else:
        print("{0}  {1}: No valid DHT22 values in this cycle".format(timestamp, label))

    if len(state["temp_values"]) >= args.samples_per_block:
        avg_temp = statistics.mean(state["temp_values"])
        avg_hum = statistics.mean(state["hum_values"])

        print("--------------------------------------------------")
        print("{0}  {1}: Average of {2} samples:".format(
            timestamp,
            label,
            args.samples_per_block
        ))
        print("Temperature: {0:6.2f} C".format(avg_temp))
        print("Humidity   : {0:6.2f} %".format(avg_hum))
        print("--------------------------------------------------")
        print()

        state["temp_values"].clear()
        state["hum_values"].clear()
        state["completed_blocks"] += 1


def main():
    args = parse_args()

    if args.mode == "both" and args.gpio1 == args.gpio2:
        print("[ERROR] In mode 'both', gpio1 and gpio2 must be different.")
        sys.exit(1)

    active_sensors = []
    if args.mode in ("sensor1", "both"):
        active_sensors.append(("Sensor1", args.gpio1))
    if args.mode in ("sensor2", "both"):
        active_sensors.append(("Sensor2", args.gpio2))

    print_header(args, active_sensors)

    sensors = {}
    states = {}

    for label, gpio_number in active_sensors:
        sensors[label] = init_sensor(gpio_number, label)
        states[label] = create_sensor_state()

    # Allow sensors to stabilize
    time.sleep(2.0)

    print("Starting measurements...")
    print()

    try:
        while True:
            all_done = True

            for label, _gpio_number in active_sensors:
                if states[label]["completed_blocks"] < args.max_blocks:
                    all_done = False
                    handle_measurement(label, sensors[label], states[label], args)

            if all_done:
                break

            time.sleep(args.interval)

    except KeyboardInterrupt:
        print("\n[INFO] Interrupted by user. Stopping DHT22 test.")

    except Exception as e:
        print("[ERROR] Unexpected error in main loop: {0}".format(e))

    finally:
        for label in sensors:
            try:
                sensors[label].exit()
            except Exception:
                pass

        print("[INFO] DHT22 test finished.")
        print("=== Test complete ===")


if __name__ == "__main__":
    main()