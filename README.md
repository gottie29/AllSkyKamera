# AllSkyKamera

Python library for all-sky cameras in the **AllSkyKamera** network  
(<https://allskykamera.space>)

Version: v2026.01.14_01

## Further documentation and Wiki

For extended guides, troubleshooting, sensor information, development notes and advanced configuration,  
please visit the official AllSkyKamera Wiki:

🔗 **https://github.com/gottie29/AllSkyKamera/wiki**

The Wiki is continuously updated and contains many additional examples and best practices.

## Description

The AllSkyKamera network is a collection of all-sky cameras at different locations.
Its goal is to provide easy access to image and sensor data, for example:

- to run environmental and astronomy projects in schools, or  
- simply to explore the night sky from different locations.

This Python library makes it possible to send images, videos and sensor data from a local
all-sky camera to the central server, where they are published via
<https://allskykamera.space>.

The library **does not modify** the standard allsky software by Thomas Jacquin and does
not change any of your local camera settings or custom scripts.  
It only reads the data and uploads it to the AllSkyKamera server.

## Requirements

Participating in the AllSkyKamera network is intentionally kept as simple as possible.

You need:

- a Raspberry Pi-based all-sky camera (Raspberry Pi 4 or newer recommended)
- the standard allsky software and web interface by Thomas Jacquin or INDI AllSky
- a working internet connection (for data upload)

To join the network you need a **secret API key**.  
You can request a key here: <https://www.allskykamera.space/machmit.php>

Without this secret key the library will not work and your camera cannot upload any data.

## Updating the library

If you already have the AllSkyKamera Python library installed, it is a good idea to
update it from time to time. New features and improvements are added continuously.

Updating is as simple as pulling the latest changes from GitHub:

1. Log in to your Raspberry Pi (SSH or local console).
2. Run the following commands:

   ```bash
   cd ~/AllSkyKamera
   git pull origin main
   ```

Existing configuration values (for example in askutils/config.py) are not
overwritten by a normal update. Only the library code and scripts tracked by Git
are updated.

## Installation / Uninstallation

Installing the Python library is straightforward.

### Installation

The installation of the Python library is split into two steps:

- `install.sh` – basic installation (packages, API key, minimal config)
- `setup.sh` – interactive configuration (camera, site, sensors, cronjobs)

1. **Download the library**

   ```bash
   cd
   git clone https://github.com/gottie29/AllSkyKamera.git
   cd AllSkyKamera
   ```
2. **Run the installer**

   ```bash
   ./install.sh
   ```

When you start the installer, all required packages for the library will be installed.
After that, the script will ask you for the necessary configuration values.

<strong>Important (privacy):</strong>
If you enter very precise location data, the map on the website will show the exact
position of your camera.
If you do not want that, simply shift your latitude and longitude by a small amount.

The final step is to upload this configuration to the server.
Once the configuration has been transferred, your camera will appear on the website.

After installation you do not need to reboot the camera, the allsky software, or
the Raspberry Pi. As soon as the cronjobs are installed, data transfer will start
automatically.

If nothing appears on the website, either the configuration has not been uploaded yet,
or the cronjobs are not running correctly.

3. **Run the setup**

   ```bash
   ./setup.sh
   ```
This script opens a text-based menu interface (using whiptail) and allows you to edit all configuration values in a safe and structured way.

**Note:**
After installation and setup you do not need to reboot the Raspberry Pi or the allsky software.
As soon as the cronjobs are active, data transfer starts automatically.

## Uninstallation

To remove the AllSkyKamera library from your Raspberry Pi, you can use the
uninstallation script:

   ```bash
   cd ~/AllSkyKamera
   ./uninstall.sh
   ```

This will:
- remove the library directory
- remove all cronjobs created by the installer

You can verify your current cron table with:

   ```bash
   crontab -l
   ```

## Cronjobs

The library uses **cronjobs** to run all recurring tasks (status updates, image uploads, sensor loggers, SQM, etc.).  
These cronjobs are written into the user’s crontab and can be viewed or edited at any time with standard tools like `crontab -l`.

### How cronjobs are created

Cronjobs are not written manually – they are generated from the `CRONTABS` list inside `askutils/config.py`.

- `install.sh` creates an initial `config.py` with a set of **base jobs**, for example:
  - Raspberry Pi status (`scripts.raspi_status`)
  - image upload (`scripts.run_image_upload`)
  - daily config upload (`scripts.upload_config_json`)
  - nightly FTP upload (`scripts.run_nightly_upload`)
  - SQM measurement and SQM plot generation

- `setup.sh` then:
  - rewrites `config.py` with all your chosen settings (camera, site, sensors, intervals),
  - **adds additional cronjobs** dynamically for each enabled sensor (`BME280`, `TSL2591`, `DS18B20`, `DHT11`, `DHT22`, `MLX90614`) and optional KpIndex,
  - and finally calls `scripts.manage_crontabs` to apply all cronjobs to your crontab.

In normal operation you do **not** need to edit cronjobs manually. You change settings via `setup.sh`, and the script regenerates both `config.py` and the cron configuration.

### Apply cronjobs manually

If you ever change `config.py` by hand, or want to reapply the cron configuration, you can run:

   ```bash
   cd ~/AllSkyKamera
   python3 -m scripts.manage_crontabs
   ```

This command:

- reads the CRONTABS list from config.py,
- removes old AllSkyKamera entries from your crontab,
- and writes the current set of jobs into the crontab.

If it succeeds, the Raspberry Pi will start sending data within the defined intervals (typically within 1–2 minutes).
The data should then appear on the network site: https://allskykamera.space

### Upload configuration to the server

For your camera to appear on the website, a minimal configuration JSON must be uploaded to the central server.
Both install.sh (optionally) and setup.sh already call this for you, but you can also trigger it manually:


   ```bash
   cd ~/AllSkyKamera
   python3 -m scripts.upload_config_json
   ```

After a successful upload:

- the camera entry is created or updated on the server,
- name, site, operator and other metadata are visible on the map and detail pages.

If your camera still does not show up:

- Check that upload_config_json ran without errors.

Verify that manage_crontabs has been executed and the jobs are present:

   ```bash
   crontab -l
   ```

## What data is transferred?

The AllSkyKamera library automatically uploads a variety of data products to the central server.  
These uploads are handled through the cron-based automation system and the FTP uploader included in the library.

### **1. Timelapse videos**
Every night a timelapse video (day-to-night or full-night depending on your allsky configuration) is created by the allsky interface.  
The library uploads this file to the server

### **2. Keograms**
A keogram is a vertical time-slice representation of the night sky, generated by the allsky interface.  
The library uploads each nightly keogram to the server.

Keograms provide a quick visual overview of cloud cover and sky transitions throughout the night and are used both in the web interface and later in data analysis.

### **3. Startrails**
Startrail images show the apparent motion of stars across the sky, created by stacking all long-exposure frames of the night.  
These files are uploaded to the server.

Startrails offer insight into sky rotation, sky quality and cloud dynamics.

---

### **4. Raw and processed auxiliary files**
Depending on the camera configuration, the library may also upload:

- `image.jpg` → current live image  
- `config.json` → camera configuration for website display  

All uploads follow the directory structure used by the AllSkyKamera server.

You can choose different file- and video-types.
The Website is working with that types.

We recommend the follow filetypes:
- MP4 for vidoe (webm is possible, but the browser buffering is not so good for webm formated files)
- JPG for images

---

## Supported sensors

The AllSkyKamera library supports a range of environmental and sky-quality sensors.  
Each sensor can be:

- **enabled/disabled** in `setup.sh`,  
- given a **custom display name**,  
- set with a **logging interval**,  
- optionally included as **overlay information** on the image.

Below is a list of all sensors currently supported:

---

### **1. BME280 (Temperature, Humidity, Pressure)**  
**Connection:** I2C (`0x76` or `0x77`)  
**Features:**  
- Temperature  
- Relative humidity  
- Air pressure  
- Optional image overlay  
- Configurable logging interval  
- Data written to InfluxDB and shown in the web UI  

Ideal for housing climate monitoring inside the camera.

---

### **2. TSL2591 (Sky Brightness / SQM Replacement)**  
**Connection:** I2C (`0x29`)  
**Features:**  
- High-sensitivity light sensor  
- Can act as a digital SQM meter  
- Supports:
  - `SQM2_LIMIT` threshold  
  - Correction factor for calibration  
  - Optional overlay in the nightly image  
- Automatic logging via cron  
- Used for cloud detection and sky brightness plots  

---

### **3. MLX90614 (Infrared Temperature Sensor)**  
**Connection:** I2C (`0x5a`)  
**Features:**  
- Measures temperature via infrared radiation  
- Detects **sky temperature** for cloud estimation  
- Optional logging and overlay  
- Excellent complement to TSL2591  

---

### **4. DHT11 (Temperature & Humidity)**  
**Connection:** GPIO (single-wire)  
**Features:**  
- Basic temperature & humidity sensor  
- Adjustable retry count and delay  
- Optional overlay  
- Good for simple internal monitoring  

---

### **5. DHT22 (Temperature & Humidity, high accuracy)**  
**Connection:** GPIO (single-wire)  
**Features:**  
- Higher precision than DHT11  
- Configurable retries and delay  
- Overlay support  
- Suitable for external or internal climate tracking  

---

### **6. DS18B20 (Temperature)**  
**Connection:** GPIO (single-wire)  
**Features:**  
- Configurable retries and delay  
- Overlay support  
- Suitable for external or internal climate tracking  

---

### **7. HTU21/GY-21/SHT21 (Temperature, Huminity)**  
**Connection:** I2C (`0x40`)  
**Features:**  
- Basic temperature & humidity sensor  
- Adjustable retry count and delay  
- Optional overlay  
- Good for simple internal monitoring    

---

### **8. SHT3x (Temperature, Huminity)**  
**Connection:** I2C (`0x44`)  
**Features:**  
- Basic temperature & humidity sensor  
- Adjustable retry count and delay  
- Optional overlay  
- Good for simple internal monitoring    

---

### **Sensor configuration**

All sensor settings are controlled via `setup.sh`:

- Enable / disable  
- Set custom names  
- Configure I2C address or GPIO pin  
- Enable overlays  
- Set logging interval  
- Write updated cronjobs  

## API Access

The AllSkyKamera ecosystem provides a dedicated and secure API for external sensors,
weather stations, microcontrollers (ESP32, ESP8266, Arduino), and custom data sources.

The API documentation is available here:

🔗 **https://allskykamera.space/api-doc.php**

The page includes:

- how to request an API key  
- authentication requirements  
- allowed request formats  
- examples for sending multiple sensor values  
- error codes and common responses  

A detailed guide, including Python and ESP32 examples, can also be found in the Wiki:

🔗 **https://github.com/gottie29/AllSkyKamera/wiki**

## Additional information

For more details about installation, sensor integration, overlays, plotting tools, backend processes,
and internal structure of the library, consult the AllSkyKamera Wiki:

🔗 **https://github.com/gottie29/AllSkyKamera/wiki**
