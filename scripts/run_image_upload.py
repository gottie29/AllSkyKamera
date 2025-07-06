# scripts/run_image_upload.py

from askutils.uploader.image_upload import upload_image

if __name__ == "__main__":
    # ohne Argument nutzt upload_image() den Pfad aus config.ALLSKY_PATH/IMAGE_PATH
    upload_image()
