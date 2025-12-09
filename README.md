# AllSkyKamera

Python library for all-sky cameras in the **AllSkyKamera** network  
(<https://allskykamera.space>)

Version: v2025.12.09_01

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
- the standard allsky software and web interface by Thomas Jacquin
- a working internet connection (for data upload)

Support for the **INDI-Allsky** interface is planned and will be added to this library
in the future.

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
