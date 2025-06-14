from askutils.utils import statusinfo

temp = statusinfo.get_temp()
disk = statusinfo.get_disk_usage()
voltage = statusinfo.get_voltage()
uptime = statusinfo.get_boot_time_seconds()

print(temp);