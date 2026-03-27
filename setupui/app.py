#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import socket
from functools import wraps
from update_service import get_version_status, run_update
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from auth_service import get_cron_settings, update_cron_settings
from sensor_service import build_sensor_overview
from options_write_service import save_kpindex_settings, save_meteor_settings
from translation import TEXTS, tr

from config_write_service import (
    save_config_values,
    list_backups,
    restore_backup,
    run_config_upload,
    test_paths,
    prune_backups_keep_latest,
    prune_old_backups,
)

from config_service import load_config_data_safe
from auth_service import (
    ui_is_initialized,
    create_initial_user,
    verify_login,
    update_credentials,
    update_language,
    get_language,
    get_username,
    verify_recovery_key,
    get_or_create_session_secret,
)

from cron_service import (
    get_desired_base_jobs,
    read_current_crontab,
    compare_base_block,
    apply_base_crontab,
    parse_base_jobs_from_block,
    validate_base_cron_settings,
    build_sensor_jobs,
    compare_sensor_block,
    apply_sensor_crontab,
    parse_sensor_jobs_from_block,
    build_option_jobs,
    compare_option_block,
    apply_option_crontab,
    parse_option_jobs_from_block,
)

from sensor_write_service import (
    save_bme280_settings,
    save_dht11_settings,
    save_dht22_settings,
    save_tsl2591_settings,
    save_ds18b20_settings,
    save_mlx90614_settings,
    save_htu21_settings,
    save_sht3x_settings,
)

from sensor_test_service import (
    test_bme280,
    test_dht11,
    test_dht22,
    test_tsl2591,
    test_ds18b20,
    test_mlx90614,
    test_htu21,
    test_sht3x,
)

app = Flask(__name__)
app.secret_key = os.environ.get("SETUPUI_SECRET_KEY", get_or_create_session_secret())

app.config["SESSION_COOKIE_NAME"] = "setupui_session"
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SECURE"] = False   # bei http über IP
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_DOMAIN"] = None    # ganz wichtig: host-only lassen

@app.context_processor
def inject_globals():
    lang = get_language()
    return {
        "ui_lang": lang,
        "tr": lambda key: tr(key, lang),
        "session_logged_in": bool(session.get("logged_in")),
        "session_username": session.get("username", ""),
    }


def login_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if not ui_is_initialized():
            return redirect(url_for("setup"))
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)
    return wrapper


def get_base_context(active_page, page_title_key):
    config_data = load_config_data_safe()
    camera = config_data.get("camera", {})
    meta = config_data.get("meta", {})
    lang = get_language()
    version_info = get_version_status()

    return {
        "hostname": socket.gethostname(),
        "camera_id": camera.get("kamera_id") or "unbekannt",
        "location_name": camera.get("standort_name") or "unbekannt",
        "active_page": active_page,
        "page_title": tr(page_title_key, lang),
        "config_data": config_data,
        "config_meta": meta,
        "version_info": version_info,
    }


@app.route("/setup", methods=["GET", "POST"])
def setup():
    if ui_is_initialized():
        return redirect(url_for("login"))

    lang = "de"

    if request.method == "POST":
        language = (request.form.get("language") or "de").strip().lower()
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        password_repeat = request.form.get("password_repeat") or ""

        lang = language if language in ("de", "en") else "de"

        if not username or not password or not password_repeat:
            flash(tr("fields_required", lang), "error")
        elif password != password_repeat:
            flash(tr("password_mismatch", lang), "error")
        else:
            create_initial_user(username, password, lang)
            flash(tr("setup_success", lang), "success")
            return redirect(url_for("login"))

    return render_template("setup.html", page_title=tr("first_setup", lang))


@app.route("/login", methods=["GET", "POST"])
def login():
    if not ui_is_initialized():
        return redirect(url_for("setup"))

    lang = get_language()

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""

        if verify_login(username, password):
            session["logged_in"] = True
            session["username"] = username
            
            try:
                prune_old_backups(max_age_days=90, keep_latest=3)
            except Exception:
                pass
            
            return redirect(url_for("dashboard"))

        flash(tr("login_failed", lang), "error")

    return render_template("login.html", page_title=tr("login", lang))


@app.route("/logout")
def logout():
    lang = get_language()
    session.clear()
    flash(tr("logout_success", lang), "success")
    return redirect(url_for("login"))


@app.route("/recover", methods=["GET", "POST"])
def recover():
    lang = get_language() if ui_is_initialized() else "de"

    if request.method == "POST":
        recovery_key = request.form.get("recovery_key") or ""
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        password_repeat = request.form.get("password_repeat") or ""

        if not recovery_key or not username or not password or not password_repeat:
            flash(tr("fields_required", lang), "error")
        elif password != password_repeat:
            flash(tr("password_mismatch", lang), "error")
        elif not verify_recovery_key(recovery_key):
            flash(tr("recover_failed", lang), "error")
        else:
            update_credentials(username, password)
            flash(tr("recover_success", lang), "success")
            return redirect(url_for("login"))

    return render_template("recover.html", page_title=tr("recover", lang))


@app.route("/")
@login_required
def dashboard():
    return render_template("dashboard.html", **get_base_context("dashboard", "dashboard"))


@app.route("/allsky-settings", methods=["GET", "POST"])
@login_required
def allsky_settings():
    if request.method == "POST":
        action = (request.form.get("action") or "").strip()

        if action == "save":
            form_data = {
                "KAMERA_NAME": request.form.get("KAMERA_NAME", ""),
                "STANDORT_NAME": request.form.get("STANDORT_NAME", ""),
                "BENUTZER_NAME": request.form.get("BENUTZER_NAME", ""),
                "KONTAKT_EMAIL": request.form.get("KONTAKT_EMAIL", ""),
                "WEBSEITE": request.form.get("WEBSEITE", ""),
                "LATITUDE": request.form.get("LATITUDE", ""),
                "LONGITUDE": request.form.get("LONGITUDE", ""),
                "ALLSKY_PATH": request.form.get("ALLSKY_PATH", ""),
                "IMAGE_BASE_PATH": request.form.get("IMAGE_BASE_PATH", ""),
                "IMAGE_PATH": request.form.get("IMAGE_PATH", ""),
                "CAMERAID": request.form.get("CAMERAID", ""),
            }

            try:
                result = save_config_values(form_data)
                if result.get("changed"):
                    flash("Settings saved locally. Backup created.", "success")
                else:
                    flash("No changes detected. Backup created.", "success")
                return redirect(url_for("allsky_settings"))
            except Exception as e:
                flash(f"Saving failed: {e}", "error")
                return redirect(url_for("allsky_settings"))

        elif action == "upload":
            try:
                upload_result = run_config_upload()
                if upload_result.get("ok"):
                    flash("Config uploaded to server successfully.", "success")
                else:
                    flash("Config upload failed: {}".format(upload_result.get("stderr") or "unknown error"), "error")
                return redirect(url_for("allsky_settings"))
            except Exception as e:
                flash(f"Upload failed: {e}", "error")
                return redirect(url_for("allsky_settings"))

        elif action == "restore":
            backup_name = (request.form.get("backup_name") or "").strip()
            if not backup_name:
                flash("Please select a backup.", "error")
                return redirect(url_for("allsky_settings"))

            try:
                restore_backup(backup_name)
                flash(f"Backup restored locally: {backup_name}", "success")
                return redirect(url_for("allsky_settings"))
            except Exception as e:
                flash(f"Restore failed: {e}", "error")
                return redirect(url_for("allsky_settings"))

        elif action == "cleanup_backups":
            try:
                cleanup = prune_backups_keep_latest(keep_latest=3)
                flash(
                    f"{cleanup['deleted_count']} old backups deleted. Latest 3 kept.",
                    "success"
                )
                return redirect(url_for("allsky_settings"))
            except Exception as e:
                flash(f"Backup cleanup failed: {e}", "error")
                return redirect(url_for("allsky_settings"))

    context = get_base_context("allsky_settings", "allsky_settings")
    context["config_backups"] = list_backups()
    return render_template("allsky_settings.html", **context)


@app.route("/sensors", methods=["GET", "POST"])
@login_required
def sensors():
    config_data = load_config_data_safe()

    if request.method == "POST":
        action = (request.form.get("action") or "").strip()

        if action == "apply_sensor_crons":
            result = apply_sensor_crontab(config_data)
            if result.get("ok"):
                flash("Sensor cronjobs applied successfully.", "success")
            else:
                flash("Applying sensor cronjobs failed: {}".format(result.get("error") or "unknown error"), "error")
            return redirect(url_for("sensors"))

    context = get_base_context("sensors", "sensors")
    context["sensor_overview"] = build_sensor_overview(context["config_data"])

    current = read_current_crontab()
    raw_crontab = current.get("raw", "") if current.get("ok") else ""
    compare = compare_sensor_block(context["config_data"], raw_crontab)

    context["sensor_cron_current_ok"] = current.get("ok", False)
    context["sensor_cron_current_error"] = current.get("error", "")
    context["sensor_cron_jobs_desired"] = build_sensor_jobs(context["config_data"])
    context["sensor_cron_jobs_current"] = parse_sensor_jobs_from_block(compare.get("current_block", ""))
    context["sensor_cron_desired_block"] = compare.get("desired_block", "")
    context["sensor_cron_current_block"] = compare.get("current_block", "")
    context["sensor_cron_in_sync"] = compare.get("in_sync", False)
    context["sensor_cron_has_current_block"] = compare.get("has_current_block", False)

    return render_template("sensors.html", **context)


@app.route("/cronjobs", methods=["GET", "POST"])
@login_required
def cronjobs():
    config_data = load_config_data_safe()

    if request.method == "POST":
        action = (request.form.get("action") or "").strip()

        if action == "save_base_cron_settings":
            try:
                image_upload_interval_min = int(request.form.get("image_upload_interval_min", "2"))
                nightly_upload_hour = int(request.form.get("nightly_upload_hour", "8"))
                nightly_upload_minute = int(request.form.get("nightly_upload_minute", "45"))
                settings_upload_interval_min = int(request.form.get("settings_upload_interval_min", "10"))
            except ValueError:
                flash("Invalid cron settings.", "error")
                return redirect(url_for("cronjobs"))

            errors = validate_base_cron_settings(
                image_upload_interval_min,
                nightly_upload_hour,
                nightly_upload_minute,
                settings_upload_interval_min,
            )

            if errors:
                flash("Cron settings invalid: " + " | ".join(errors.values()), "error")
                return redirect(url_for("cronjobs"))

            update_cron_settings(
                image_upload_interval_min,
                nightly_upload_hour,
                nightly_upload_minute,
                settings_upload_interval_min,
            )
            flash("Base cron settings saved.", "success")
            return redirect(url_for("cronjobs"))

        elif action == "apply_base_crons":
            result = apply_base_crontab(config_data)
            if result.get("ok"):
                flash("Base cronjobs applied successfully.", "success")
            else:
                flash("Applying base cronjobs failed: {}".format(result.get("error") or "unknown error"), "error")
            return redirect(url_for("cronjobs"))

    context = get_base_context("cronjobs", "cronjobs")

    current = read_current_crontab()
    raw_crontab = current.get("raw", "") if current.get("ok") else ""
    compare = compare_base_block(config_data, raw_crontab)

    context["cron_current_ok"] = current.get("ok", False)
    context["cron_current_error"] = current.get("error", "")
    context["cron_has_crontab"] = current.get("has_crontab", False)

    context["cron_desired_jobs"] = get_desired_base_jobs(config_data)
    context["cron_current_jobs"] = parse_base_jobs_from_block(compare.get("current_block", ""))
    context["cron_desired_block"] = compare.get("desired_block", "")
    context["cron_current_block"] = compare.get("current_block", "")
    context["cron_in_sync"] = compare.get("in_sync", False)
    context["cron_has_current_block"] = compare.get("has_current_block", False)
    context["cron_settings"] = get_cron_settings()

    return render_template("cronjobs.html", **context)


@app.route("/kpindex", methods=["GET", "POST"])
@login_required
def kpindex():
    config_data = load_config_data_safe()

    if request.method == "POST":
        action = (request.form.get("action") or "").strip()

        if action == "save_kpindex":
            try:
                payload = {
                    "enabled": request.form.get("enabled") == "1",
                    "overlay": request.form.get("overlay") == "1",
                    "log_interval_min": int(request.form.get("log_interval_min") or "15"),
                }
                save_kpindex_settings(payload)
                flash("KpIndex settings saved locally.", "success")
            except Exception as e:
                flash("Saving KpIndex settings failed: %s" % e, "error")
            return redirect(url_for("kpindex"))

        elif action == "apply_option_crons":
            result = apply_option_crontab(config_data)
            if result.get("ok"):
                flash("Option cronjobs applied successfully.", "success")
            else:
                flash("Applying option cronjobs failed: {}".format(result.get("error") or "unknown error"), "error")
            return redirect(url_for("kpindex"))

    context = get_base_context("kpindex", "kpindex")

    current = read_current_crontab()
    raw_crontab = current.get("raw", "") if current.get("ok") else ""
    compare = compare_option_block(context["config_data"], raw_crontab)

    context["option_cron_jobs_desired"] = build_option_jobs(context["config_data"])
    context["option_cron_jobs_current"] = parse_option_jobs_from_block(compare.get("current_block", ""))
    context["option_cron_desired_block"] = compare.get("desired_block", "")
    context["option_cron_current_block"] = compare.get("current_block", "")
    context["option_cron_in_sync"] = compare.get("in_sync", False)
    context["option_cron_has_current_block"] = compare.get("has_current_block", False)
    context["option_cron_current_ok"] = current.get("ok", False)
    context["option_cron_current_error"] = current.get("error", "")

    return render_template("kpindex.html", **context)

@app.route("/meteor", methods=["GET", "POST"])
@login_required
def meteor():
    config_data = load_config_data_safe()

    if request.method == "POST":
        action = (request.form.get("action") or "").strip()

        if action == "save_meteor":
            try:
                payload = {
                    "enabled": request.form.get("enabled") == "1",
                    "output_dir": request.form.get("output_dir", ""),
                    "state_file": request.form.get("state_file", ""),
                    "keep_days_local": request.form.get("keep_days_local", "3"),
                    "threshold": request.form.get("threshold", "80"),
                    "min_pixels": request.form.get("min_pixels", "1200"),
                    "min_blob_pixels": request.form.get("min_blob_pixels", "25"),
                    "min_line_length": request.form.get("min_line_length", "20"),
                    "min_aspect_ratio": request.form.get("min_aspect_ratio", "4.0"),
                    "fullhd_width": request.form.get("fullhd_width", "1920"),
                    "small_width": request.form.get("small_width", "640"),
                    "diff_width": request.form.get("diff_width", "640"),
                    "boxed_width": request.form.get("boxed_width", "640"),
                    "prev_small_width": request.form.get("prev_small_width", "640"),
                    "upload_jitter_max_seconds": request.form.get("upload_jitter_max_seconds", "90"),
                }
                save_meteor_settings(payload)
                flash("Meteor settings saved locally.", "success")
            except Exception as e:
                flash("Saving meteor settings failed: %s" % e, "error")
            return redirect(url_for("meteor"))

        elif action == "apply_option_crons":
            result = apply_option_crontab(config_data)
            if result.get("ok"):
                flash("Option cronjobs applied successfully.", "success")
            else:
                flash("Applying option cronjobs failed: {}".format(result.get("error") or "unknown error"), "error")
            return redirect(url_for("meteor"))

    context = get_base_context("meteor", "meteor")

    current = read_current_crontab()
    raw_crontab = current.get("raw", "") if current.get("ok") else ""
    compare = compare_option_block(context["config_data"], raw_crontab)

    context["option_cron_jobs_desired"] = build_option_jobs(context["config_data"])
    context["option_cron_jobs_current"] = parse_option_jobs_from_block(compare.get("current_block", ""))
    context["option_cron_desired_block"] = compare.get("desired_block", "")
    context["option_cron_current_block"] = compare.get("current_block", "")
    context["option_cron_in_sync"] = compare.get("in_sync", False)
    context["option_cron_has_current_block"] = compare.get("has_current_block", False)
    context["option_cron_current_ok"] = current.get("ok", False)
    context["option_cron_current_error"] = current.get("error", "")

    return render_template("meteor.html", **context)


@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    lang = get_language()

    if request.method == "POST":
        action = (request.form.get("action") or "").strip()

        if action == "change_credentials":
            current_password = request.form.get("current_password") or ""
            new_username = (request.form.get("new_username") or "").strip()
            new_password = request.form.get("new_password") or ""
            new_password_repeat = request.form.get("new_password_repeat") or ""

            current_username = get_username()

            if not current_password or not new_username or not new_password or not new_password_repeat:
                flash(tr("fields_required", lang), "error")
                return redirect(url_for("settings"))

            if new_password != new_password_repeat:
                flash(tr("password_mismatch", lang), "error")
                return redirect(url_for("settings"))

            if not verify_login(current_username, current_password):
                flash("Aktuelles Passwort ist falsch.", "error")
                return redirect(url_for("settings"))

            try:
                update_credentials(new_username, new_password)
                session["username"] = new_username
                flash("Benutzername und Passwort wurden erfolgreich geändert.", "success")
            except Exception as e:
                flash("Änderung fehlgeschlagen: %s" % e, "error")

            return redirect(url_for("settings"))

    context = get_base_context("settings", "settings")
    context["stored_username"] = get_username()
    return render_template("settings.html", **context)

@app.route("/set-language/<lang>")
@login_required
def set_language(lang):
    lang = (lang or "").strip().lower()
    if lang in ("de", "en"):
        update_language(lang)
    return redirect(request.referrer or url_for("dashboard"))


@app.route("/health")
def health():
    return {"status": "ok", "service": "setupui"}

@app.route("/check-update")
@login_required
def check_update():
    return redirect(url_for("settings"))


@app.route("/run-update", methods=["POST"])
@login_required
def run_update_route():
    lang = get_language()
    result = run_update()

    if result.get("ok"):
        flash("Update erfolgreich gestartet. Die WebUI wird neu gestartet.", "success")
    else:
        msg = result.get("error") or "Update fehlgeschlagen."
        flash(msg, "error")

    return redirect(url_for("settings"))

@app.route("/test-paths", methods=["POST"])
@login_required
def test_paths_route():
    try:
        allsky_path = request.form.get("ALLSKY_PATH", "")
        image_base_path = request.form.get("IMAGE_BASE_PATH", "")
        image_path = request.form.get("IMAGE_PATH", "")
        cameraid = request.form.get("CAMERAID", "")

        config_data = load_config_data_safe()
        indi = bool(config_data.get("system", {}).get("indi", False))

        result = test_paths(
            allsky_path,
            image_base_path,
            image_path,
            indi=indi,
            cameraid=cameraid,
        )

        return jsonify({
            "ok": True,
            "result": result
        })

    except Exception as e:
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500
        
@app.route("/save-sensor-settings", methods=["POST"])
@login_required
def save_sensor_settings():
    sensor_type = (request.form.get("sensor_type") or "").strip().lower()

    try:
        if sensor_type == "bme280":
            payload = {
                "enabled": request.form.get("enabled") == "1",
                "mode": (request.form.get("mode") or "single").strip(),
                "log_interval_min": int(request.form.get("log_interval_min") or "1"),
                "items": []
            }

            if payload["mode"] == "multi":
                count = int(request.form.get("item_count") or "0")
                for i in range(count):
                    payload["items"].append({
                        "enabled": request.form.get("item_enabled_%d" % i) == "1",
                        "name": request.form.get("item_name_%d" % i, ""),
                        "address": request.form.get("item_address_%d" % i, ""),
                        "overlay": request.form.get("item_overlay_%d" % i) == "1",
                        "temp_offset_c": request.form.get("item_temp_offset_c_%d" % i, "0"),
                        "press_offset_hpa": request.form.get("item_press_offset_hpa_%d" % i, "0"),
                        "hum_offset_pct": request.form.get("item_hum_offset_pct_%d" % i, "0"),
                    })
            else:
                payload["items"].append({
                    "enabled": request.form.get("item_enabled_0") == "1",
                    "name": request.form.get("item_name_0", ""),
                    "address": request.form.get("item_address_0", ""),
                    "overlay": request.form.get("item_overlay_0") == "1",
                    "temp_offset_c": request.form.get("item_temp_offset_c_0", "0"),
                    "press_offset_hpa": request.form.get("item_press_offset_hpa_0", "0"),
                    "hum_offset_pct": request.form.get("item_hum_offset_pct_0", "0"),
                })

            save_bme280_settings(payload)
            flash("BME280 settings saved locally.", "success")

        elif sensor_type == "mlx90614":
            payload = {
                "enabled": request.form.get("enabled") == "1",
                "log_interval_min": int(request.form.get("log_interval_min") or "1"),
                "items": [{
                    "name": request.form.get("item_name_0", ""),
                    "address": request.form.get("item_address_0", "0x5a"),
                    "ambient_offset_c": request.form.get("item_ambient_offset_c_0", "0"),
                    "cloud_k1": request.form.get("item_cloud_k1_0", "0"),
                    "cloud_k2": request.form.get("item_cloud_k2_0", "0"),
                    "cloud_k3": request.form.get("item_cloud_k3_0", "0"),
                    "cloud_k4": request.form.get("item_cloud_k4_0", "0"),
                    "cloud_k5": request.form.get("item_cloud_k5_0", "0"),
                    "cloud_k6": request.form.get("item_cloud_k6_0", "0"),
                    "cloud_k7": request.form.get("item_cloud_k7_0", "0"),
                }]
            }

            save_mlx90614_settings(payload)
            flash("MLX90614 settings saved locally.", "success")

        elif sensor_type == "dht11":
            payload = {
                "enabled": request.form.get("enabled") == "1",
                "log_interval_min": int(request.form.get("log_interval_min") or "1"),
                "items": [{
                    "enabled": request.form.get("item_enabled_0") == "1",
                    "name": request.form.get("item_name_0", ""),
                    "gpio_bcm": request.form.get("item_gpio_bcm_0", "0"),
                    "retries": request.form.get("item_retries_0", "5"),
                    "retry_delay": request.form.get("item_retry_delay_0", "0.3"),
                    "overlay": request.form.get("item_overlay_0") == "1",
                    "temp_offset_c": request.form.get("item_temp_offset_c_0", "0"),
                    "hum_offset_pct": request.form.get("item_hum_offset_pct_0", "0"),
                }]
            }

            save_dht11_settings(payload)
            flash("DHT11 settings saved locally.", "success")

        elif sensor_type == "dht22":
            payload = {
                "enabled": request.form.get("enabled") == "1",
                "mode": (request.form.get("mode") or "single").strip(),
                "log_interval_min": int(request.form.get("log_interval_min") or "1"),
                "items": []
            }

            if payload["mode"] == "multi":
                count = int(request.form.get("item_count") or "0")
                for i in range(count):
                    payload["items"].append({
                        "enabled": request.form.get("item_enabled_%d" % i) == "1",
                        "name": request.form.get("item_name_%d" % i, ""),
                        "gpio_bcm": request.form.get("item_gpio_bcm_%d" % i, "0"),
                        "retries": request.form.get("item_retries_%d" % i, "5"),
                        "retry_delay": request.form.get("item_retry_delay_%d" % i, "0.3"),
                        "overlay": request.form.get("item_overlay_%d" % i) == "1",
                        "temp_offset_c": request.form.get("item_temp_offset_c_%d" % i, "0"),
                        "hum_offset_pct": request.form.get("item_hum_offset_pct_%d" % i, "0"),
                    })
            else:
                payload["items"].append({
                    "enabled": request.form.get("item_enabled_0") == "1",
                    "name": request.form.get("item_name_0", ""),
                    "gpio_bcm": request.form.get("item_gpio_bcm_0", "0"),
                    "retries": request.form.get("item_retries_0", "5"),
                    "retry_delay": request.form.get("item_retry_delay_0", "0.3"),
                    "overlay": request.form.get("item_overlay_0") == "1",
                    "temp_offset_c": request.form.get("item_temp_offset_c_0", "0"),
                    "hum_offset_pct": request.form.get("item_hum_offset_pct_0", "0"),
                })

            save_dht22_settings(payload)
            flash("DHT22 settings saved locally.", "success")

        elif sensor_type == "ds18b20":
            payload = {
                "enabled": request.form.get("enabled") == "1",
                "log_interval_min": int(request.form.get("log_interval_min") or "1"),
                "items": [{
                    "enabled": request.form.get("item_enabled_0") == "1",
                    "name": request.form.get("item_name_0", ""),
                    "overlay": request.form.get("item_overlay_0") == "1",
                    "temp_offset_c": request.form.get("item_temp_offset_c_0", "0"),
                }]
            }

            save_ds18b20_settings(payload)
            flash("DS18B20 settings saved locally.", "success")

        elif sensor_type == "tsl2591":
            payload = {
                "enabled": request.form.get("enabled") == "1",
                "log_interval_min": int(request.form.get("log_interval_min") or "1"),
                "items": [{
                    "name": request.form.get("item_name_0", ""),
                    "address": request.form.get("item_address_0", ""),
                    "overlay": request.form.get("item_overlay_0") == "1",
                    "sqm2_limit": request.form.get("item_sqm2_limit_0", "0"),
                    "sqm_correction": request.form.get("item_sqm_correction_0", "0"),
                }]
            }

            save_tsl2591_settings(payload)
            flash("TSL2591 settings saved locally.", "success")

        elif sensor_type == "htu21":
            payload = {
                "enabled": request.form.get("enabled") == "1",
                "log_interval_min": int(request.form.get("log_interval_min") or "1"),
                "items": [{
                    "name": request.form.get("item_name_0", ""),
                    "address": request.form.get("item_address_0", "0x40"),
                    "overlay": request.form.get("item_overlay_0") == "1",
                    "temp_offset": request.form.get("item_temp_offset_0", "0"),
                    "hum_offset": request.form.get("item_hum_offset_0", "0"),
                }]
            }

            save_htu21_settings(payload)
            flash("HTU21 settings saved locally.", "success")

        elif sensor_type == "sht3x":
            payload = {
                "enabled": request.form.get("enabled") == "1",
                "log_interval_min": int(request.form.get("log_interval_min") or "1"),
                "items": [{
                    "name": request.form.get("item_name_0", ""),
                    "address": request.form.get("item_address_0", "0x44"),
                    "overlay": request.form.get("item_overlay_0") == "1",
                    "temp_offset": request.form.get("item_temp_offset_0", "0"),
                    "hum_offset": request.form.get("item_hum_offset_0", "0"),
                }]
            }

            save_sht3x_settings(payload)
            flash("SHT3X settings saved locally.", "success")

        else:
            flash("Unsupported sensor type.", "error")

    except Exception as e:
        flash("Saving sensor settings failed: %s" % e, "error")

    return redirect(url_for("sensors"))

@app.route("/test-sensor", methods=["POST"])
@login_required
def test_sensor():
    sensor_type = (request.form.get("sensor_type") or "").strip().lower()

    try:
        if sensor_type == "bme280":
            result = test_bme280(request.form.get("address", "0x76"))
        elif sensor_type == "tsl2591":
            result = test_tsl2591(request.form.get("address", "0x29"))
        elif sensor_type == "dht11":
            result = test_dht11(
                request.form.get("gpio_bcm", "6"),
                request.form.get("retries", "5"),
                request.form.get("retry_delay", "0.3"),
            )            
        elif sensor_type == "dht22":
            result = test_dht22(
                request.form.get("gpio_bcm", "6"),
                request.form.get("retries", "5"),
                request.form.get("retry_delay", "0.3"),
            )
        elif sensor_type == "mlx90614":
            result = test_mlx90614(request.form.get("address", "0x5a"))            
        elif sensor_type == "ds18b20":
            result = test_ds18b20()
        elif sensor_type == "htu21":
            result = test_htu21(request.form.get("address", "0x40"))
        elif sensor_type == "sht3x":
            result = test_sht3x(request.form.get("address", "0x44"))
        else:
            result = {"ok": False, "error": "Unsupported sensor type"}

        return jsonify(result)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/debug-session")
def debug_session():
    from flask import request, session
    return {
        "host": request.host,
        "cookies": dict(request.cookies),
        "session": dict(session),
        "secret_key_len": len(str(app.secret_key)) if app.secret_key else 0,
    }

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=False)