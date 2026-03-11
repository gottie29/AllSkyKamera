#!/usr/bin/env python3
import sys
from datetime import datetime
from askutils.uploader.nightly_upload_api import upload_nightly_batch


def _parse_date_arg(arg: str) -> str:
    try:
        dt = datetime.strptime(arg, "%Y%m%d")
    except ValueError:
        print("Fehler: Datum muss im Format JJJJMMTT angegeben werden, z.B. 20260310.", flush=True)
        sys.exit(1)
    return dt.strftime("%Y%m%d")


def main() -> None:
    if len(sys.argv) > 2 or (len(sys.argv) == 2 and sys.argv[1] in ("-h", "--help")):
        print(
            "Verwendung:\n"
            "  python3 -m scripts.run_nightly_upload_api\n"
            "    -> laedt die letzte Nacht (gestern) hoch\n\n"
            "  python3 -m scripts.run_nightly_upload_api 20260310\n"
            "    -> laedt genau dieses Datum hoch\n",
            flush=True,
        )
        sys.exit(0 if len(sys.argv) == 2 else 1)

    date_str = None
    if len(sys.argv) == 2:
        date_str = _parse_date_arg(sys.argv[1])

    success = upload_nightly_batch(date_str)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()