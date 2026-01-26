import sys
from askutils.uploader import config_upload

no_jitter = "--no-jitter" in sys.argv

json_path = config_upload.create_config_json()
if json_path:
    config_upload.upload_to_ftp(json_path, use_jitter=not no_jitter)
