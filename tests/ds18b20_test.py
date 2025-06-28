import os
import glob
import time

def read_ds18b20():
    base_dir = '/sys/bus/w1/devices/'
    device_folders = glob.glob(base_dir + '28-*')
    if not device_folders:
        return None, "❌ Kein DS18B20-Sensor gefunden"

    device_file = device_folders[0] + '/w1_slave'
    
    try:
        with open(device_file, 'r') as f:
            lines = f.readlines()

        if lines[0].strip()[-3:] != 'YES':
            return None, "❌ CRC-Fehler beim Lesen"

        equals_pos = lines[1].find('t=')
        if equals_pos != -1:
            temp_string = lines[1][equals_pos+2:]
            temperature_c = float(temp_string) / 1000.0
            return temperature_c, None
    except Exception as e:
        return None, f"❌ Fehler: {e}"

    return None, "❌ Unerwartetes Fehlerformat"

# Hauptprogramm
if __name__ == "__main__":
    while True:
        temp, err = read_ds18b20()
        if err:
            print(err)
        else:
            print(f"🌡️ Temperatur: {temp:.2f} °C")
        time.sleep(2)
