# AllSkyKamera

Python client for all-sky cameras in the **AllSkyKamera** network  
(<https://allskykamera.space>)

Version: v2026.03.27_01

## Overview

The AllSkyKamera network collects images, videos and sensor data from all-sky
cameras at different locations. The goal is to make sky and environmental data
available for schools, astronomy projects and interested observers.

This repository contains the Raspberry Pi client. It reads data from an existing
all-sky installation and uploads it to the AllSkyKamera server. It supports both:

- Thomas Jacquin allsky
- INDI AllSky

The client does not modify the core allsky camera software. It reads generated
images, videos, metadata and sensor values, then transfers them to
<https://allskykamera.space>.

## Requirements

You need:

- Raspberry Pi 4 or newer recommended
- Raspberry Pi OS with internet access
- Thomas Jacquin allsky or INDI AllSky already installed
- API key for the AllSkyKamera network

You can request an API key here:

<https://www.allskykamera.space/machmit.php>

Without this API key the client cannot fetch upload credentials and cannot send
data to the central server.

## Installation

Clone the repository and run the installer:

```bash
cd
git clone https://github.com/gottie29/AllSkyKamera.git
cd AllSkyKamera
./install.sh
```

The installer performs the initial setup:

- checks whether an existing `askutils/config.py` or `askutils/ASKsecret.py`
  exists and offers to back it up
- asks for your API key and validates it against the AllSkyKamera server
- asks whether you use Thomas Jacquin allsky or INDI AllSky
- detects the relevant image path or camera directory where possible
- installs required system packages
- enables I2C, 1-Wire and camera support where supported by the system
- installs Python dependencies
- creates `askutils/ASKsecret.py`
- creates an initial `askutils/config.py`
- uploads the first camera configuration
- installs base cronjobs
- installs and starts the local SetupUI as a systemd service

After installation, open the SetupUI in your browser:

```text
http://<raspberry-pi-ip>:5001
```

The installer prints detected network addresses at the end, for example:

```text
SetupUI: http://192.168.1.23:5001
```

### First SetupUI Login

On first access, the SetupUI asks you to create a local user account. This
account is only for the local Raspberry Pi web interface.

The SetupUI can then be used to manage:

- camera and location settings
- allsky paths
- sensor settings
- sensor tests
- cronjobs
- KpIndex and meteor detection options
- config upload
- local config backups
- update checks

Important privacy note: precise latitude and longitude values can reveal the
exact camera location on the public map. If you do not want that, shift the
coordinates slightly before uploading the configuration.

## Optional Text Setup

The older text-based setup is still available:

```bash
cd ~/AllSkyKamera
./setup.sh
```

It uses `whiptail` and can edit camera, site, sensor and cron settings from the
terminal. For most users, the web-based SetupUI is now the easier path.

## Updating

You can update from the command line:

```bash
cd ~/AllSkyKamera
git pull origin main
```

Local configuration files such as `askutils/config.py`, `askutils/ASKsecret.py`,
`config.json` and SetupUI data are ignored by Git and should not be overwritten
by a normal update.

The SetupUI also contains update-related functionality. If an update was pulled
while the SetupUI service is running, restart it with:

```bash
sudo systemctl restart allsky-setupui.service
```

## Service Management

The installer creates this systemd service:

```text
allsky-setupui.service
```

Useful commands:

```bash
sudo systemctl status allsky-setupui.service
sudo systemctl restart allsky-setupui.service
sudo systemctl stop allsky-setupui.service
sudo systemctl start allsky-setupui.service
```

The web interface runs on port `5001`.

## Cronjobs

All recurring tasks are executed through cronjobs. The installer writes the base
cronjobs immediately after creating the initial configuration.

Typical base jobs are:

- Raspberry Pi status upload
- live image upload
- daily configuration upload
- nightly upload of videos and processed assets
- SQM measurement

Additional jobs are created for enabled sensors and optional features such as
KpIndex or meteor detection.

You can inspect the current crontab with:

```bash
crontab -l
```

You can reapply cronjobs manually:

```bash
cd ~/AllSkyKamera
python3 -m scripts.manage_crontabs
```

The SetupUI also shows desired and installed cronjobs and can apply them from
the browser.

## Uploads

The current upload scripts use the AllSkyKamera API for live images and nightly
assets. Depending on the camera type and configuration, the client uploads:

- live image variants: full HD, mobile and thumbnail
- nightly timelapse videos
- keograms
- startrail images
- startrail timelapse videos where supported
- camera configuration metadata
- Raspberry Pi status
- sensor values
- optional KpIndex and meteor detection data

Recommended file formats:

- JPG or PNG for source images
- MP4 for videos

WebM is supported in parts of the code, but MP4 is usually better for browser
playback and buffering.

## Supported Sensors

The client supports these sensors:

- BME280: temperature, humidity, pressure; supports multi-sensor configuration
- TSL2591: sky brightness / SQM-style measurements
- MLX90614: infrared sky temperature
- DHT11: temperature and humidity
- DHT22: temperature and humidity; supports multi-sensor configuration
- DS18B20: temperature
- HTU21 / GY-21 / SHT21: temperature and humidity
- SHT3x: temperature and humidity

Sensor settings can be managed in the SetupUI or with `setup.sh`. Depending on
the sensor, settings include:

- enabled / disabled
- display name
- I2C address or GPIO pin
- logging interval
- offset values
- overlay output
- sensor test

Sensor values are written to InfluxDB through the credentials fetched from the
AllSkyKamera API.

## Manual Commands

Upload the current public configuration:

```bash
cd ~/AllSkyKamera
python3 -m scripts.upload_config_json
```

Run the live image upload manually:

```bash
cd ~/AllSkyKamera
python3 -m scripts.run_image_upload_indi_api
```

For Thomas Jacquin allsky installations use:

```bash
cd ~/AllSkyKamera
python3 -m scripts.run_image_upload_tj_api
```

Run the nightly upload manually:

```bash
cd ~/AllSkyKamera
python3 -m scripts.run_nightly_upload_indi_api
```

For Thomas Jacquin allsky installations use:

```bash
cd ~/AllSkyKamera
python3 -m scripts.run_nightly_upload_tj_api
```

## Uninstallation

To remove the client, run:

```bash
cd ~/AllSkyKamera
./uninstall.sh
```

Afterwards, verify your crontab:

```bash
crontab -l
```

If the SetupUI service was installed, also check:

```bash
sudo systemctl status allsky-setupui.service
```

## API Access

The AllSkyKamera ecosystem provides an API for cameras, external sensors,
weather stations, microcontrollers and custom data sources.

API documentation:

<https://allskykamera.space/api-doc.php>

It includes:

- API key usage
- authentication requirements
- allowed request formats
- examples for sending sensor values
- error codes and common responses

## Documentation and Wiki

More documentation, examples and troubleshooting notes are available in the
project Wiki:

<https://github.com/gottie29/AllSkyKamera/wiki>
