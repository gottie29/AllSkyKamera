import requests

def load_remote_secrets(api_key, api_url):
    try:
        response = requests.get(api_url, params={"key": api_key}, timeout=5)
        response.raise_for_status()
        secrets = response.json()

        if "error" in secrets:
            raise ValueError("Serverfehler: " + secrets["error"])

        return {
            "INFLUX_URL": secrets.get("influx_url"),
            "INFLUX_TOKEN": secrets.get("influx_token"),
            "INFLUX_ORG": secrets.get("influx_org"),
            "INFLUX_BUCKET": secrets.get("influx_bucket"),
            "FTP_USER": secrets.get("ftp_user"),
            "FTP_PASS": secrets.get("ftp_pass"),
            "FTP_SERVER": secrets.get("ftp_server"),
            "FTP_REMOTE_DIR": secrets.get("kamera_id"),
            "KAMERA_ID": secrets.get("kamera_id"),
        }

    except Exception as e:
        print("❌ Fehler beim Laden der Secrets:", e)
        return None
