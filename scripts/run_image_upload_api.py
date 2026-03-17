# scripts/run_image_upload_api.py

from askutils.uploader.image_upload_api import upload_image_api

if __name__ == "__main__":
    upload_image_api()
    
def upload_image_api(date=None):
    return upload_nightly_batch(date)