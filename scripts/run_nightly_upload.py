# scripts/run_nightly_upload.py

from askutils.uploader.nightly_upload import upload_nightly_batch

if __name__ == "__main__":
    # ohne Argument wird automatisch der Vortag hochgeladen
    upload_nightly_batch()
