#!/usr/bin/env python3
import sys
from datetime import datetime
from askutils.uploader.manual_upload import upload_manual_batch


def _parse_date_arg(arg: str) -> str:
    """
    Erwartet JJJJMMTT, z.B. 20251119.
    Gibt denselben String zurueck, wenn er ein gueltiges Datum repraesentiert,
    sonst beendet es das Script mit Fehlercode.
    """
    try:
        dt = datetime.strptime(arg, "%Y%m%d")
    except ValueError:
        print("Fehler: Datum muss im Format JJJJMMTT angegeben werden, z.B. 20251119.", flush=True)
        sys.exit(1)
    return dt.strftime("%Y%m%d")


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] in ("-h", "--help"):
        print(
            "Verwendung:\n"
            "  python3 -m scripts.run_manual_upload 20251119\n"
            "    -> laedt Video/Keogram/Startrail/Analemma fuer diesen Tag hoch\n",
            flush=True,
        )
        if len(sys.argv) != 2:
            sys.exit(1)
        sys.exit(0)

    raw = sys.argv[1]
    date_str = _parse_date_arg(raw)
    print(f"Starte MANUELLEN Upload fuer Datum {date_str} ...", flush=True)

    success = upload_manual_batch(date_str)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
