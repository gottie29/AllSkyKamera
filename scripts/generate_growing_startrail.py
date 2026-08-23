#!/usr/bin/env python3

import argparse
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image

from askutils import config


MASK_PATH = (
    "/home/pi/AllSkyKamera/tmp/growing_startrail_mask/"
    "ASK002-tj-overlay-mask.png"
)

OUTPUT_DIR = "/home/pi/AllSkyKamera/tmp/growing_startrail_mask"

TJ_SETTINGS_PATH = "/home/pi/allsky/config/settings.json"

DEFAULT_FPS = 20
DEFAULT_LIMIT = 0
OUTPUT_WIDTH = 1920


def log(msg):
    print(f"[GROWING-STARTRAIL] {msg}", flush=True)


def get_tj_brightness_threshold():
    """
    Liest den Startrail-Helligkeitsthreshold direkt aus der
    TJ-AllSky settings.json.

    Beispiel:
        "startrailsbrightnessthreshold": 0.35

    Rückgabewert:
        float 0.0 ... 1.0
    """

    try:
        with open(TJ_SETTINGS_PATH, "r", encoding="utf-8") as f:
            settings = json.load(f)

        value = float(
            settings.get(
                "startrailsbrightnessthreshold",
                0.35
            )
        )

        if value < 0.0 or value > 1.0:
            raise ValueError(
                f"Ungültiger TJ-Threshold: {value}"
            )

        return value

    except Exception as e:
        raise RuntimeError(
            f"TJ Startrail-Threshold konnte nicht gelesen werden: {e}"
        )


def get_image_root():
    """
    Gleiche Pfadlogik wie im bestehenden Nightly-Uploader.
    """

    allsky_path = getattr(
        config,
        "ALLSKY_PATH",
        ""
    ) or ""

    image_base_path = getattr(
        config,
        "IMAGE_BASE_PATH",
        ""
    ) or ""

    if image_base_path:
        return os.path.abspath(
            os.path.join(
                allsky_path,
                image_base_path
            )
        )

    return os.path.abspath(
        allsky_path
    )


def find_images(date_str):
    """
    Sucht alle Einzelbilder einer Nacht.
    """

    image_root = get_image_root()

    night_dir = os.path.join(
        image_root,
        date_str
    )

    log(f"IMAGE_ROOT: {image_root}")
    log(f"Nachtverzeichnis: {night_dir}")

    if not os.path.isdir(night_dir):
        raise RuntimeError(
            f"Nachtverzeichnis existiert nicht: {night_dir}"
        )

    pattern = os.path.join(
        night_dir,
        "image-*.jpg"
    )

    files = sorted(
        glob.glob(pattern)
    )

    if not files:
        raise RuntimeError(
            f"Keine Einzelbilder gefunden: {pattern}"
        )

    return night_dir, files


def load_mask(target_size):
    """
    Lädt die Overlay-Maske.

    Weiß / >127:
        Overlaybereich, der NICHT kumuliert wird.

    Schwarz / <=127:
        Bereich für Startrail-Kumulation.
    """

    if not os.path.isfile(MASK_PATH):
        raise RuntimeError(
            f"Maske nicht gefunden: {MASK_PATH}"
        )

    with Image.open(MASK_PATH) as img:
        mask = img.convert("L")

        if mask.size != target_size:
            log(
                f"Maske {mask.size} passt nicht zu "
                f"Bild {target_size}; Maske wird skaliert."
            )

            mask = mask.resize(
                target_size,
                Image.Resampling.NEAREST
            )

        mask_arr = np.asarray(
            mask
        )

    return mask_arr > 127


def calculate_brightness(current_arr):
    """
    TJ-AllSky-kompatible Helligkeitsberechnung.

    Entspricht der Logik aus startrails.cpp:

        cv::Scalar mean_scalar = cv::mean(imagesrc);

        Bei Farbe:
            Maximum der drei Farbkanal-Mittelwerte

        Bei 8 Bit:
            Division durch 255.0

    Rückgabewert:
        0.0 ... 1.0
    """

    if current_arr.ndim == 2:
        image_mean = float(
            current_arr.mean()
        )

    elif (
        current_arr.ndim == 3
        and current_arr.shape[2] >= 3
    ):
        means = current_arr.mean(
            axis=(0, 1)
        )

        image_mean = float(
            np.max(
                means[:3]
            )
        )

    else:
        raise RuntimeError(
            f"Unbekanntes Bildformat: shape={current_arr.shape}"
        )

    return image_mean / 255.0


def create_frame(
    current_arr,
    accumulated_arr,
    overlay_mask
):
    """
    Erzeugt einen neuen Growing-Startrail-Frame.

    Nicht maskierter Bereich:
        pixelweises Maximum aus bisherigem Startrail
        und aktuellem Einzelbild.

    Maskierter Bereich:
        immer aktuelle Pixel aus dem Originalbild.
    """

    accumulated_arr = np.maximum(
        accumulated_arr,
        current_arr
    )

    output_arr = accumulated_arr.copy()

    # Aktuelle Overlay-Informationen übernehmen.
    output_arr[
        overlay_mask
    ] = current_arr[
        overlay_mask
    ]

    # Auch im Akkumulator keine alten Overlay-Inhalte behalten.
    accumulated_arr[
        overlay_mask
    ] = current_arr[
        overlay_mask
    ]

    return (
        accumulated_arr,
        output_arr
    )


def save_frame(
    arr,
    path
):
    """
    Speichert einen temporären JPEG-Videoframe.
    """

    img = Image.fromarray(
        arr.astype(
            np.uint8
        ),
        mode="RGB"
    )

    img.save(
        path,
        format="JPEG",
        quality=92,
        subsampling=0
    )


def create_video(
    frame_dir,
    output_file,
    fps
):
    """
    Erzeugt aus den temporären JPEG-Frames ein kompatibles
    Full-HD-H.264-Video.
    """

    pattern = os.path.join(
        frame_dir,
        "frame-%06d.jpg"
    )

    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "warning",
        "-y",

        "-framerate",
        str(fps),

        "-i",
        pattern,

        "-vf",
        f"scale={OUTPUT_WIDTH}:-2",

        "-c:v",
        "libx264",

        "-profile:v",
        "main",

        "-preset",
        "medium",

        "-crf",
        "23",

        "-pix_fmt",
        "yuv420p",

        "-movflags",
        "+faststart",

        "-an",

        output_file,
    ]

    log("Starte ffmpeg ...")
    log(" ".join(cmd))

    subprocess.check_call(
        cmd
    )


def analyse_brightness(
    image_files,
    threshold
):
    """
    Analysiert alle Bilder einer Nacht mit exakt derselben
    Helligkeitslogik wie TJ-AllSky.
    """

    log("")
    log("---- HELLIGKEITSANALYSE ----")
    log(
        f"TJ Threshold: {threshold:.3f}"
    )
    log("")

    values = []

    for index, image_path in enumerate(
        image_files,
        start=1
    ):

        with Image.open(image_path) as img:
            img = img.convert("RGB")

            current_arr = np.asarray(
                img,
                dtype=np.uint8
            )

        brightness = calculate_brightness(
            current_arr
        )

        if brightness <= threshold:
            state = "USE "
        else:
            state = "SKIP"

        filename = os.path.basename(
            image_path
        )

        log(
            f"{index:4d} "
            f"brightness={brightness:7.3f} "
            f"{state} "
            f"{filename}"
        )

        values.append(
            (
                brightness,
                image_path
            )
        )

    if not values:
        return

    brightness_values = [
        value
        for value, _ in values
    ]

    usable = [
        value
        for value in brightness_values
        if value <= threshold
    ]

    skipped = (
        len(brightness_values)
        - len(usable)
    )

    log("")
    log("---- STATISTIK ----")

    log(
        f"Minimum: {min(brightness_values):.3f}"
    )

    log(
        f"Maximum: {max(brightness_values):.3f}"
    )

    log(
        f"Mittel:  {np.mean(brightness_values):.3f}"
    )

    log(
        f"Median:  {np.median(brightness_values):.3f}"
    )

    log(
        f"Threshold: {threshold:.3f}"
    )

    log(
        f"Verwendbar: {len(usable)}"
    )

    log(
        f"Übersprungen: {skipped}"
    )

    log("----------------------------")


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Erzeugt ein wachsendes Startrail-Video "
            "mit TJ-Overlay-Maske und TJ-kompatiblem "
            "Helligkeitsfilter."
        )
    )

    parser.add_argument(
        "date",
        help=(
            "Nacht im Format YYYYMMDD, "
            "z.B. 20260822"
        )
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help=(
            "Maximale Anzahl Eingangsbilder. "
            "0 = alle Bilder."
        )
    )

    parser.add_argument(
        "--fps",
        type=int,
        default=DEFAULT_FPS,
        help=(
            f"Video-FPS "
            f"(Default: {DEFAULT_FPS})"
        )
    )

    parser.add_argument(
        "--threshold",
        type=float,
        default=None,
        help=(
            "TJ-kompatible maximale Bildhelligkeit "
            "von 0.0 bis 1.0. "
            "Ohne Angabe wird "
            "'startrailsbrightnessthreshold' "
            "aus TJ settings.json verwendet."
        )
    )

    parser.add_argument(
        "--analyse-brightness",
        action="store_true",
        help=(
            "Nur die TJ-kompatible Helligkeit "
            "aller Bilder analysieren. "
            "Es wird kein Video erzeugt."
        )
    )

    parser.add_argument(
        "--keep-frames",
        action="store_true",
        help=(
            "Temporäre JPEG-Frames "
            "nach Videoerstellung behalten."
        )
    )

    args = parser.parse_args()

    # -------------------------------------------
    # Datum prüfen
    # -------------------------------------------

    if (
        len(args.date) != 8
        or not args.date.isdigit()
    ):
        raise RuntimeError(
            "Datum muss im Format YYYYMMDD angegeben werden."
        )

    # -------------------------------------------
    # Threshold bestimmen
    # -------------------------------------------

    tj_threshold = (
        get_tj_brightness_threshold()
    )

    if args.threshold is None:
        threshold = tj_threshold

        log(
            f"Brightness Threshold aus TJ settings.json: "
            f"{threshold:.3f}"
        )

    else:
        threshold = args.threshold

        if (
            threshold < 0.0
            or threshold > 1.0
        ):
            raise RuntimeError(
                "Threshold muss zwischen 0.0 und 1.0 liegen."
            )

        log(
            f"Brightness Threshold per Argument: "
            f"{threshold:.3f}"
        )

        log(
            f"TJ settings.json Threshold wäre: "
            f"{tj_threshold:.3f}"
        )

    # -------------------------------------------
    # Bilder suchen
    # -------------------------------------------

    night_dir, image_files = find_images(
        args.date
    )

    if args.limit > 0:
        image_files = image_files[
            :args.limit
        ]

    log(
        f"Gefundene/verwendete Eingangsbilder: "
        f"{len(image_files)}"
    )

    if not image_files:
        raise RuntimeError(
            "Keine Bilder vorhanden."
        )

    # -------------------------------------------
    # Bildgröße ermitteln
    # -------------------------------------------

    with Image.open(
        image_files[0]
    ) as first:

        first = first.convert(
            "RGB"
        )

        image_size = first.size

    width, height = image_size

    log(
        f"Bildgröße: {width} x {height}"
    )

    log(
        f"Erstes Eingangsbild: "
        f"{image_files[0]}"
    )

    log(
        f"Letztes Eingangsbild: "
        f"{image_files[-1]}"
    )

    log(
        f"Maske: {MASK_PATH}"
    )

    # -------------------------------------------
    # Analysemodus
    # -------------------------------------------

    if args.analyse_brightness:

        analyse_brightness(
            image_files,
            threshold
        )

        return

    # -------------------------------------------
    # Maske laden
    # -------------------------------------------

    overlay_mask = load_mask(
        image_size
    )

    # -------------------------------------------
    # Ausgabe vorbereiten
    # -------------------------------------------

    os.makedirs(
        OUTPUT_DIR,
        exist_ok=True
    )

    output_file = os.path.join(
        OUTPUT_DIR,
        f"growing-startrails-"
        f"{args.date}-test-fullhd.mp4"
    )

    temp_dir = tempfile.mkdtemp(
        prefix="growing_startrail_"
    )

    log(
        f"Temporäre Frames: {temp_dir}"
    )

    accumulated_arr = None

    output_index = 0

    skipped_brightness = 0
    skipped_size = 0

    first_used_image = None
    last_used_image = None

    try:

        # ---------------------------------------
        # Bilder verarbeiten
        # ---------------------------------------

        for input_index, image_path in enumerate(
            image_files,
            start=1
        ):

            with Image.open(
                image_path
            ) as current:

                current = current.convert(
                    "RGB"
                )

                if current.size != image_size:

                    log(
                        f"SKIP falsche Bildgröße: "
                        f"{image_path} "
                        f"{current.size}"
                    )

                    skipped_size += 1
                    continue

                current_arr = np.asarray(
                    current,
                    dtype=np.uint8
                ).copy()

            # -----------------------------------
            # TJ-kompatible Helligkeit
            # -----------------------------------

            brightness = calculate_brightness(
                current_arr
            )

            if brightness > threshold:

                skipped_brightness += 1

                log(
                    f"SKIP brightness="
                    f"{brightness:.3f} > "
                    f"{threshold:.3f} "
                    f"{os.path.basename(image_path)}"
                )

                continue

            # -----------------------------------
            # Erstes brauchbares Bild
            # -----------------------------------

            if accumulated_arr is None:

                accumulated_arr = (
                    current_arr.copy()
                )

                output_arr = (
                    current_arr.copy()
                )

                first_used_image = (
                    image_path
                )

                log(
                    f"START Startrail mit "
                    f"{os.path.basename(image_path)} "
                    f"brightness={brightness:.3f}"
                )

            else:

                (
                    accumulated_arr,
                    output_arr
                ) = create_frame(
                    current_arr,
                    accumulated_arr,
                    overlay_mask
                )

            # -----------------------------------
            # Videoframe speichern
            # -----------------------------------

            output_index += 1

            last_used_image = (
                image_path
            )

            frame_path = os.path.join(
                temp_dir,
                f"frame-{output_index:06d}.jpg"
            )

            save_frame(
                output_arr,
                frame_path
            )

            if (
                output_index == 1
                or output_index % 10 == 0
            ):

                log(
                    f"Frame {output_index} "
                    f"brightness={brightness:.3f} "
                    f"aus "
                    f"{os.path.basename(image_path)}"
                )

        # ---------------------------------------
        # Prüfen
        # ---------------------------------------

        if output_index < 2:

            raise RuntimeError(
                "Nach dem Helligkeitsfilter sind "
                "weniger als zwei brauchbare Bilder übrig."
            )

        # ---------------------------------------
        # Statistik
        # ---------------------------------------

        log("")
        log("---- FILTERERGEBNIS ----")

        log(
            f"Eingangsbilder: "
            f"{len(image_files)}"
        )

        log(
            f"Verwendete Bilder: "
            f"{output_index}"
        )

        log(
            f"Zu hell übersprungen: "
            f"{skipped_brightness}"
        )

        log(
            f"Falsche Größe übersprungen: "
            f"{skipped_size}"
        )

        log(
            f"Threshold: "
            f"{threshold:.3f}"
        )

        if first_used_image:

            log(
                f"Erstes verwendetes Bild: "
                f"{first_used_image}"
            )

        if last_used_image:

            log(
                f"Letztes verwendetes Bild: "
                f"{last_used_image}"
            )

        log("------------------------")
        log("")

        # ---------------------------------------
        # MP4 erzeugen
        # ---------------------------------------

        create_video(
            temp_dir,
            output_file,
            args.fps
        )

        log("")
        log("FERTIG")

        log(
            f"Video: {output_file}"
        )

    finally:

        if args.keep_frames:

            log(
                f"Frames bleiben erhalten: "
                f"{temp_dir}"
            )

        else:

            shutil.rmtree(
                temp_dir,
                ignore_errors=True
            )


if __name__ == "__main__":

    try:

        main()

    except KeyboardInterrupt:

        log(
            "Abbruch durch Benutzer."
        )

        sys.exit(130)

    except Exception as e:

        log(
            f"FEHLER: {e}"
        )

        sys.exit(1)
