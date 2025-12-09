#!/usr/bin/env python3
import os
import sys
import ftplib

# Make sure we can import askutils from the project root
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
sys.path.insert(0, PROJECT_ROOT)

from askutils import config
from askutils.uploader.image_upload import upload_image


def test_config() -> None:
    """Check that all required configuration values are present."""
    required = [
        "FTP_SERVER",
        "FTP_USER",
        "FTP_PASS",
        "FTP_REMOTE_DIR",
        "ALLSKY_PATH",
        "IMAGE_BASE_PATH",
        "IMAGE_PATH",
    ]
    missing = [var for var in required if not getattr(config, var, None)]
    if missing:
        print(f"Missing configuration values: {', '.join(missing)}")
        sys.exit(1)
    print("All required configuration values are present.")


def test_ftp_connection() -> None:
    """Test basic FTP connectivity (login + cwd + listing)."""
    try:
        ftp = ftplib.FTP(config.FTP_SERVER, timeout=10)
        ftp.login(config.FTP_USER, config.FTP_PASS)
        print("FTP login successful on AllSkyKamera server.")

        ftp.cwd(config.FTP_REMOTE_DIR)
        print(f"Changed to remote directory '{config.FTP_REMOTE_DIR}' successfully.")

        try:
            listing = ftp.nlst()
        except Exception:
            listing = []
        print(f"Current remote directory listing: {listing}")

        ftp.quit()
    except Exception as e:
        print(f"FTP connection or directory access failed: {e}")
        sys.exit(1)


def test_image_upload() -> None:
    """
    Test the image upload function.

    Important:
    - We only check that upload_image() returns successfully.
    - We DO NOT try to delete the remote file, because upload_image()
      will typically use a fixed filename (e.g. image.jpg) that is
      used by the camera in production.
    """
    # Create dummy file in the tmp directory
    tmp_dir = os.path.join(config.ALLSKY_PATH, config.IMAGE_PATH)
    os.makedirs(tmp_dir, exist_ok=True)

    test_file = os.path.join(tmp_dir, "ftp_upload_test.txt")
    with open(test_file, "w", encoding="utf-8") as f:
        f.write("AllSkyKamera FTP upload test\n")
    print(f"Created local test file: {test_file}")

    # Run upload via the normal upload function
    try:
        success = upload_image(test_file)
    except Exception as e:
        print(f"upload_image() raised an exception: {e}")
        sys.exit(1)

    if not success:
        print("upload_image() reported failure.")
        sys.exit(1)

    print("upload_image() returned successfully.")
    print("Note: The remote file is not deleted on purpose, because it may use the production filename (e.g. image.jpg).")


if __name__ == "__main__":
    print("== 1. Checking configuration ==")
    test_config()

    print("\n== 2. Testing FTP connection ==")
    test_ftp_connection()

    print("\n== 3. Testing image upload function ==")
    test_image_upload()

    print("\nAll FTP tests finished successfully.")
