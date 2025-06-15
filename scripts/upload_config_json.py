from askutils.uploader import config_upload

json_path = config_upload.create_config_json()
if json_path:
    config_upload.upload_to_ftp(json_path)
