import datetime

def log(message):
    """Gibt eine normale Lognachricht mit Zeitstempel aus."""
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[INFO]  {timestamp} - {message}")

def warn(message):
    """Gibt eine Warnung mit Zeitstempel aus."""
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[WARN]  {timestamp} - {message}")

def error(message):
    """Gibt eine Fehlermeldung mit Zeitstempel aus."""
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[ERROR] {timestamp} - {message}")
