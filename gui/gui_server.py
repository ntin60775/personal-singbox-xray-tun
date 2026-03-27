#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import pwd
import re
import subprocess
import threading
from dataclasses import dataclass
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


GUI_DIR = Path(__file__).resolve().parent
SETTINGS_BASENAME = ".xray-tun-subvost-gui.json"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8421
ACTION_LOCK = threading.Lock()
GUI_VERSION = "2026-03-27-compact-v2"


def discover_project_root() -> Path:
    explicit_root = os.environ.get("SUBVOST_PROJECT_ROOT")
    if explicit_root:
        candidate = Path(explicit_root)
        if not candidate.is_absolute():
            raise SystemExit(f"SUBVOST_PROJECT_ROOT должен быть абсолютным путём: {explicit_root}")
        if not candidate.is_dir():
            raise SystemExit(f"SUBVOST_PROJECT_ROOT не найден: {explicit_root}")
        return candidate

    candidate = GUI_DIR.parent
    if candidate.is_dir():
        return candidate

    raise SystemExit(f"Не удалось определить корень bundle рядом с {GUI_DIR}")


def discover_real_user() -> tuple[str, Path]:
    explicit_user = os.environ.get("SUBVOST_REAL_USER")
    if explicit_user:
        explicit_home = os.environ.get("SUBVOST_REAL_HOME")
        if explicit_home:
            return explicit_user, Path(explicit_home)
        pw_entry = pwd.getpwnam(explicit_user)
        return explicit_user, Path(pw_entry.pw_dir)

    sudo_user = os.environ.get("SUDO_USER")
    if sudo_user:
        pw_entry = pwd.getpwnam(sudo_user)
        return sudo_user, Path(pw_entry.pw_dir)

    pkexec_uid = os.environ.get("PKEXEC_UID")
    if pkexec_uid and pkexec_uid.isdigit():
        pw_entry = pwd.getpwuid(int(pkexec_uid))
        return pw_entry.pw_name, Path(pw_entry.pw_dir)

    user = os.environ.get("USER") or pwd.getpwuid(os.getuid()).pw_name
    pw_entry = pwd.getpwnam(user)
    return user, Path(pw_entry.pw_dir)


PROJECT_ROOT = discover_project_root()
RUN_SCRIPT = PROJECT_ROOT / "run-xray-tun-subvost.sh"
STOP_SCRIPT = PROJECT_ROOT / "stop-xray-tun-subvost.sh"
DIAG_SCRIPT = PROJECT_ROOT / "capture-xray-tun-state.sh"
LOG_DIR = PROJECT_ROOT / "logs"
XRAY_CONFIG_PATH = PROJECT_ROOT / "xray-tun-subvost.json"
SINGBOX_CONFIG_PATH = PROJECT_ROOT / "singbox-tun-subvost.json"
REAL_USER, REAL_HOME = discover_real_user()
REAL_PW_ENTRY = pwd.getpwnam(REAL_USER)
REAL_UID = REAL_PW_ENTRY.pw_uid
REAL_GID = REAL_PW_ENTRY.pw_gid
STATE_FILE = REAL_HOME / ".xray-tun-subvost.state"
RESOLV_BACKUP = REAL_HOME / ".xray-tun-subvost.resolv.conf.backup"
SETTINGS_FILE = REAL_HOME / SETTINGS_BASENAME
LAST_ACTION: dict[str, Any] = {
    "name": None,
    "ok": None,
    "message": "GUI готов. Действия выполняются через существующие shell-скрипты.",
    "timestamp": None,
    "details": "",
}


INDEX_HTML = """<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="subvost-gui-version" content=\"""" + GUI_VERSION + """\">
  <title>Subvost Xray TUN Control</title>
  <style>
    :root {
      --bg: #f3f7fb;
      --bg-deep: #e7eef8;
      --panel: rgba(255, 255, 255, 0.82);
      --panel-strong: rgba(255, 255, 255, 0.96);
      --line: rgba(30, 41, 59, 0.1);
      --text: #132238;
      --muted: #5b6b80;
      --primary: #2563eb;
      --primary-soft: rgba(37, 99, 235, 0.12);
      --accent: #f97316;
      --accent-soft: rgba(249, 115, 22, 0.12);
      --success: #0f9f6e;
      --success-soft: rgba(15, 159, 110, 0.14);
      --danger: #dc2626;
      --danger-soft: rgba(220, 38, 38, 0.12);
      --warning: #b45309;
      --shadow: 0 18px 60px rgba(18, 36, 61, 0.10);
      --radius-xl: 28px;
      --radius-lg: 20px;
      --radius-md: 16px;
      --radius-sm: 12px;
      --mono: "IBM Plex Mono", "DejaVu Sans Mono", monospace;
      --sans: "IBM Plex Sans", "Noto Sans", "Segoe UI", sans-serif;
    }

    * {
      box-sizing: border-box;
    }

    html, body {
      margin: 0;
      min-height: 100%;
      background:
        radial-gradient(circle at top left, rgba(37, 99, 235, 0.18), transparent 32%),
        radial-gradient(circle at 85% 20%, rgba(249, 115, 22, 0.12), transparent 24%),
        linear-gradient(180deg, var(--bg) 0%, #f8fbfe 48%, var(--bg-deep) 100%);
      color: var(--text);
      font-family: var(--sans);
    }

    body::before {
      content: "";
      position: fixed;
      inset: 0;
      background-image:
        linear-gradient(rgba(19, 34, 56, 0.04) 1px, transparent 1px),
        linear-gradient(90deg, rgba(19, 34, 56, 0.04) 1px, transparent 1px);
      background-size: 36px 36px;
      mask-image: linear-gradient(180deg, rgba(0, 0, 0, 0.28), transparent 70%);
      pointer-events: none;
    }

    main {
      position: relative;
      width: min(1880px, calc(100vw - 24px));
      margin: 0 auto;
      padding: 14px 0 18px;
    }

    .hero,
    .card {
      position: relative;
      overflow: hidden;
      border: 1px solid var(--line);
      background: var(--panel);
      backdrop-filter: blur(18px);
      -webkit-backdrop-filter: blur(18px);
      box-shadow: var(--shadow);
    }

    .hero {
      border-radius: var(--radius-xl);
      padding: 22px;
      display: grid;
      grid-template-columns: minmax(300px, 1.05fr) minmax(640px, 1.55fr);
      gap: 18px;
      align-items: stretch;
    }

    .hero::after,
    .card::after {
      content: "";
      position: absolute;
      inset: auto auto -60px -60px;
      width: 140px;
      height: 140px;
      border-radius: 50%;
      background: radial-gradient(circle, rgba(37, 99, 235, 0.12), transparent 70%);
      pointer-events: none;
    }

    .hero-intro {
      display: grid;
      align-content: center;
      gap: 12px;
    }

    .hero-side {
      display: grid;
      gap: 12px;
      align-content: start;
    }

    .hero-top {
      display: flex;
      justify-content: flex-end;
      align-items: center;
      gap: 12px;
    }

    .eyebrow {
      margin: 0 0 10px;
      color: var(--primary);
      font-size: 0.78rem;
      font-weight: 700;
      letter-spacing: 0.18em;
      text-transform: uppercase;
    }

    h1 {
      margin: 0;
      max-width: 10ch;
      font-size: clamp(2.2rem, 4vw, 4.1rem);
      line-height: 0.9;
      letter-spacing: -0.05em;
    }

    .hero-copy {
      margin: 0;
      max-width: 46ch;
      color: var(--muted);
      font-size: 0.95rem;
      line-height: 1.55;
    }

    .status-pill {
      display: inline-flex;
      align-items: center;
      gap: 10px;
      min-height: 42px;
      padding: 8px 14px;
      border-radius: 999px;
      background: var(--panel-strong);
      border: 1px solid var(--line);
      color: var(--text);
      font-size: 0.9rem;
      font-weight: 700;
      white-space: nowrap;
    }

    .status-dot {
      width: 12px;
      height: 12px;
      border-radius: 50%;
      background: var(--warning);
      box-shadow: 0 0 0 6px rgba(180, 83, 9, 0.12);
      transition: background-color 180ms ease, box-shadow 180ms ease;
    }

    .status-pill[data-state="running"] .status-dot {
      background: var(--success);
      box-shadow: 0 0 0 6px var(--success-soft);
    }

    .status-pill[data-state="stopped"] .status-dot {
      background: var(--danger);
      box-shadow: 0 0 0 6px var(--danger-soft);
    }

    .hero-meta {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 10px;
    }

    .metric {
      padding: 14px 16px;
      border-radius: var(--radius-lg);
      border: 1px solid var(--line);
      background: rgba(248, 250, 252, 0.74);
      min-height: 88px;
    }

    .metric-label {
      display: block;
      margin-bottom: 8px;
      color: var(--muted);
      font-size: 0.74rem;
      font-weight: 600;
      letter-spacing: 0.06em;
      text-transform: uppercase;
    }

    .metric-value {
      font-size: 1.22rem;
      font-weight: 700;
      letter-spacing: -0.03em;
    }

    .metric-sub {
      margin-top: 4px;
      color: var(--muted);
      font-size: 0.84rem;
      line-height: 1.35;
    }

    .actions {
      display: grid;
      grid-template-columns: 1.2fr 1fr 1.2fr;
      gap: 10px;
    }

    button,
    .switch input {
      font: inherit;
    }

    .button {
      position: relative;
      border: 0;
      min-height: 54px;
      padding: 14px 18px;
      border-radius: 16px;
      font-size: 0.98rem;
      font-weight: 700;
      cursor: pointer;
      transition:
        transform 180ms ease,
        opacity 180ms ease,
        background-color 180ms ease,
        box-shadow 180ms ease;
    }

    .button:hover {
      transform: translateY(-1px);
    }

    .button:active {
      transform: translateY(0);
    }

    .button:focus-visible,
    .switch input:focus-visible + .switch-ui {
      outline: 3px solid rgba(37, 99, 235, 0.28);
      outline-offset: 2px;
    }

    .button[disabled] {
      cursor: not-allowed;
      opacity: 0.55;
      transform: none;
    }

    .button-primary {
      color: #fff;
      background: linear-gradient(135deg, #1d4ed8, #2563eb 55%, #3b82f6 100%);
      box-shadow: 0 16px 28px rgba(37, 99, 235, 0.28);
    }

    .button-accent {
      color: #fff;
      background: linear-gradient(135deg, #ea580c, #f97316 55%, #fb923c 100%);
      box-shadow: 0 16px 28px rgba(249, 115, 22, 0.26);
    }

    .button-danger {
      color: #991b1b;
      background: linear-gradient(180deg, #fff7f7, #fee2e2);
      border: 1px solid rgba(220, 38, 38, 0.18);
    }

    .grid {
      display: grid;
      grid-template-columns: 1.2fr 1fr;
      gap: 14px;
      margin-top: 14px;
    }

    .stack {
      display: grid;
      grid-template-rows: repeat(2, minmax(0, 1fr));
      gap: 14px;
      min-height: 0;
    }

    .card {
      border-radius: var(--radius-xl);
      padding: 18px;
      display: flex;
      flex-direction: column;
      min-height: 0;
    }

    .card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      margin-bottom: 12px;
    }

    .card-title {
      margin: 0;
      font-size: 1rem;
      letter-spacing: -0.03em;
    }

    .card-copy {
      margin: 4px 0 0;
      color: var(--muted);
      font-size: 0.84rem;
      line-height: 1.45;
    }

    .info-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
    }

    .info-item {
      padding: 12px 13px;
      border-radius: 14px;
      background: rgba(248, 250, 252, 0.9);
      border: 1px solid rgba(30, 41, 59, 0.08);
    }

    .info-label {
      display: block;
      margin-bottom: 6px;
      color: var(--muted);
      font-size: 0.7rem;
      font-weight: 700;
      letter-spacing: 0.06em;
      text-transform: uppercase;
    }

    .info-value {
      font-size: 0.9rem;
      line-height: 1.4;
      word-break: break-word;
    }

    .mono {
      font-family: var(--mono);
      font-size: 0.84rem;
    }

    .switch-card {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 16px;
      margin-bottom: 12px;
      padding: 14px;
      border-radius: 16px;
      background: linear-gradient(180deg, rgba(37, 99, 235, 0.08), rgba(255, 255, 255, 0.72));
      border: 1px solid rgba(37, 99, 235, 0.12);
    }

    .switch-card p {
      margin: 4px 0 0;
      color: var(--muted);
      line-height: 1.45;
      font-size: 0.82rem;
    }

    .switch {
      position: relative;
      width: 66px;
      min-width: 66px;
      height: 38px;
    }

    .switch input {
      position: absolute;
      inset: 0;
      opacity: 0;
      cursor: pointer;
      margin: 0;
    }

    .switch-ui {
      display: block;
      width: 100%;
      height: 100%;
      border-radius: 999px;
      background: rgba(91, 107, 128, 0.28);
      border: 1px solid rgba(91, 107, 128, 0.16);
      transition: background-color 180ms ease;
    }

    .switch-ui::after {
      content: "";
      position: absolute;
      top: 4px;
      left: 4px;
      width: 28px;
      height: 28px;
      border-radius: 50%;
      background: #fff;
      box-shadow: 0 8px 18px rgba(19, 34, 56, 0.18);
      transition: transform 180ms ease;
    }

    .switch input:checked + .switch-ui {
      background: linear-gradient(135deg, #2563eb, #3b82f6);
    }

    .switch input:checked + .switch-ui::after {
      transform: translateX(28px);
    }

    .badge-row {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 10px;
    }

    .badge {
      display: inline-flex;
      align-items: center;
      min-height: 30px;
      padding: 6px 10px;
      border-radius: 999px;
      background: rgba(19, 34, 56, 0.05);
      color: var(--text);
      font-size: 0.8rem;
      font-weight: 600;
    }

    .badge[data-tone="accent"] {
      background: var(--accent-soft);
      color: var(--warning);
    }

    .badge[data-tone="success"] {
      background: var(--success-soft);
      color: var(--success);
    }

    .badge[data-tone="danger"] {
      background: var(--danger-soft);
      color: var(--danger);
    }

    .output-panel {
      margin: 0;
      min-height: 132px;
      max-height: 180px;
      overflow: auto;
      padding: 14px;
      border-radius: 16px;
      background: #0f172a;
      color: #d7e3f6;
      border: 1px solid rgba(148, 163, 184, 0.16);
      font-family: var(--mono);
      font-size: 0.82rem;
      line-height: 1.55;
      white-space: pre-wrap;
      word-break: break-word;
    }

    .footer-note {
      margin-top: 10px;
      color: var(--muted);
      font-size: 0.84rem;
      line-height: 1.45;
    }

    @media (max-width: 1360px) {
      .hero {
        grid-template-columns: 1fr;
      }

      .hero-top {
        justify-content: flex-start;
      }
    }

    @media (max-width: 1100px) {
      .grid,
      .hero-meta,
      .actions,
      .info-grid {
        grid-template-columns: 1fr;
      }

      .stack {
        grid-template-rows: none;
      }
    }

    @media (max-width: 640px) {
      main {
        width: calc(100vw - 16px);
        padding: 8px 0 16px;
      }

      .hero,
      .card {
        padding: 16px;
      }

      .hero-copy {
        max-width: none;
      }

      .status-pill {
        width: 100%;
        justify-content: center;
      }
    }

    @media (prefers-reduced-motion: reduce) {
      *, *::before, *::after {
        animation-duration: 0.01ms !important;
        animation-iteration-count: 1 !important;
        transition-duration: 0.01ms !important;
        scroll-behavior: auto !important;
      }
    }
  </style>
</head>
<body>
  <main>
    <section class="hero">
      <div class="hero-intro">
        <div>
          <p class="eyebrow">Subvost Xray TUN</p>
          <h1>Локальный пульт управления туннелем</h1>
        </div>
        <p class="hero-copy">
          Старт, стоп, диагностика и ключевой статус на одном экране без ручного обновления и без лишней прокрутки.
        </p>
      </div>

      <div class="hero-side">
        <div class="hero-top">
          <div class="status-pill" id="status-pill" data-state="unknown" aria-live="polite">
            <span class="status-dot" aria-hidden="true"></span>
            <span id="status-pill-text">Проверяю состояние</span>
          </div>
        </div>

        <div class="hero-meta">
          <div class="metric">
            <span class="metric-label">Стек</span>
            <div class="metric-value" id="hero-stack">-</div>
            <div class="metric-sub" id="hero-stack-sub">Ожидание данных</div>
          </div>
          <div class="metric">
            <span class="metric-label">TUN / DNS</span>
            <div class="metric-value" id="hero-tun">-</div>
            <div class="metric-sub" id="hero-dns">Ожидание данных</div>
          </div>
          <div class="metric">
            <span class="metric-label">Логи</span>
            <div class="metric-value" id="hero-logs">-</div>
            <div class="metric-sub" id="hero-logs-sub">Ожидание данных</div>
          </div>
        </div>

        <div class="actions" aria-label="Основные действия">
          <button class="button button-primary" id="start-button" type="button">Старт</button>
          <button class="button button-danger" id="stop-button" type="button">Стоп</button>
          <button class="button button-accent" id="diag-button" type="button">Снять диагностику</button>
        </div>
      </div>
    </section>

    <section class="grid">
      <div class="stack">
        <article class="card">
          <div class="card-header">
            <div>
              <h2 class="card-title">Состояние и управление</h2>
              <p class="card-copy">Статус процессов, TUN-интерфейса и режим логирования.</p>
            </div>
          </div>

          <div class="switch-card">
            <div>
              <strong>Файловое логирование</strong>
              <p>Применяется при следующем старте. Текущую активную сессию переключатель не перезапускает.</p>
            </div>
            <label class="switch" aria-label="Включить файловое логирование">
              <input type="checkbox" id="logging-toggle">
              <span class="switch-ui" aria-hidden="true"></span>
            </label>
          </div>

          <div class="info-grid">
            <div class="info-item">
              <span class="info-label">Статус</span>
              <div class="info-value" id="state-summary">-</div>
            </div>
            <div class="info-item">
              <span class="info-label">Режим запуска</span>
              <div class="info-value" id="runtime-mode">-</div>
            </div>
            <div class="info-item">
              <span class="info-label">Xray PID</span>
              <div class="info-value mono" id="xray-pid">-</div>
            </div>
            <div class="info-item">
              <span class="info-label">sing-box PID</span>
              <div class="info-value mono" id="singbox-pid">-</div>
            </div>
          </div>

          <div class="badge-row" id="state-badges"></div>
        </article>

        <article class="card">
          <div class="card-header">
            <div>
              <h2 class="card-title">Минимум по соединению</h2>
              <p class="card-copy">Точка выхода, локальные порты, TUN и DNS без перегруза деталями.</p>
            </div>
          </div>

          <div class="info-grid">
            <div class="info-item">
              <span class="info-label">Удалённый узел</span>
              <div class="info-value mono" id="remote-host">-</div>
            </div>
            <div class="info-item">
              <span class="info-label">SNI / Host</span>
              <div class="info-value mono" id="remote-sni">-</div>
            </div>
            <div class="info-item">
              <span class="info-label">SOCKS / Mixed</span>
              <div class="info-value mono" id="local-ports">-</div>
            </div>
            <div class="info-item">
              <span class="info-label">TUN адрес</span>
              <div class="info-value mono" id="tun-address">-</div>
            </div>
            <div class="info-item">
              <span class="info-label">Интерфейс</span>
              <div class="info-value mono" id="tun-interface">-</div>
            </div>
            <div class="info-item">
              <span class="info-label">DNS</span>
              <div class="info-value mono" id="dns-servers">-</div>
            </div>
          </div>
        </article>
      </div>

      <div class="stack">
        <article class="card">
          <div class="card-header">
            <div>
              <h2 class="card-title">Диагностика</h2>
              <p class="card-copy">Последний дамп и служебные файлы, которые пригодятся при разборе сбоев.</p>
            </div>
          </div>

          <div class="info-grid">
            <div class="info-item">
              <span class="info-label">Последняя диагностика</span>
              <div class="info-value mono" id="latest-diagnostic">-</div>
            </div>
            <div class="info-item">
              <span class="info-label">State file</span>
              <div class="info-value mono" id="state-file">-</div>
            </div>
            <div class="info-item">
              <span class="info-label">Backup resolv.conf</span>
              <div class="info-value mono" id="resolv-backup">-</div>
            </div>
            <div class="info-item">
              <span class="info-label">Логи</span>
              <div class="info-value mono" id="log-files">-</div>
            </div>
          </div>
        </article>

        <article class="card">
          <div class="card-header">
            <div>
              <h2 class="card-title">Последнее действие и вывод</h2>
              <p class="card-copy">Короткий итог операции и хвост stdout/stderr без отдельного нижнего блока.</p>
            </div>
          </div>
          <div class="info-grid">
            <div class="info-item">
              <span class="info-label">Операция</span>
              <div class="info-value" id="last-action-name">-</div>
            </div>
            <div class="info-item">
              <span class="info-label">Когда</span>
              <div class="info-value mono" id="last-action-time">-</div>
            </div>
          </div>
          <div class="badge-row" id="action-badges"></div>
          <p class="footer-note" id="last-action-message">GUI готов.</p>
          <pre class="output-panel" id="command-output" aria-live="polite">Ожидание данных...</pre>
        </article>
      </div>
    </section>
  </main>

  <script>
    const state = {
      polling: null,
      busy: false,
    };

    const els = {
      startButton: document.getElementById("start-button"),
      stopButton: document.getElementById("stop-button"),
      diagButton: document.getElementById("diag-button"),
      loggingToggle: document.getElementById("logging-toggle"),
      statusPill: document.getElementById("status-pill"),
      statusPillText: document.getElementById("status-pill-text"),
      heroStack: document.getElementById("hero-stack"),
      heroStackSub: document.getElementById("hero-stack-sub"),
      heroTun: document.getElementById("hero-tun"),
      heroDns: document.getElementById("hero-dns"),
      heroLogs: document.getElementById("hero-logs"),
      heroLogsSub: document.getElementById("hero-logs-sub"),
      stateSummary: document.getElementById("state-summary"),
      runtimeMode: document.getElementById("runtime-mode"),
      xrayPid: document.getElementById("xray-pid"),
      singboxPid: document.getElementById("singbox-pid"),
      stateBadges: document.getElementById("state-badges"),
      remoteHost: document.getElementById("remote-host"),
      remoteSni: document.getElementById("remote-sni"),
      localPorts: document.getElementById("local-ports"),
      tunAddress: document.getElementById("tun-address"),
      tunInterface: document.getElementById("tun-interface"),
      dnsServers: document.getElementById("dns-servers"),
      latestDiagnostic: document.getElementById("latest-diagnostic"),
      stateFile: document.getElementById("state-file"),
      resolvBackup: document.getElementById("resolv-backup"),
      logFiles: document.getElementById("log-files"),
      lastActionName: document.getElementById("last-action-name"),
      lastActionTime: document.getElementById("last-action-time"),
      actionBadges: document.getElementById("action-badges"),
      lastActionMessage: document.getElementById("last-action-message"),
      commandOutput: document.getElementById("command-output"),
    };

    function setBusy(busy) {
      state.busy = busy;
      for (const button of [els.startButton, els.stopButton, els.diagButton]) {
        button.disabled = busy;
      }
      els.loggingToggle.disabled = busy;
    }

    function formatTimestamp(value) {
      if (!value) return "—";
      const date = new Date(value);
      if (Number.isNaN(date.getTime())) return value;
      return date.toLocaleString("ru-RU");
    }

    function escapeHtml(value) {
      return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;");
    }

    function badge(label, tone = "") {
      const attr = tone ? ` data-tone="${tone}"` : "";
      return `<span class="badge"${attr}>${escapeHtml(label)}</span>`;
    }

    function renderBadges(container, items) {
      container.innerHTML = items.join("");
    }

    function compactPathValue(value) {
      if (!value || value === "—") return "—";
      return value
        .split(",")
        .map((item) => {
          const trimmed = item.trim();
          const parts = trimmed.split("/");
          return parts[parts.length - 1] || trimmed;
        })
        .join(", ");
    }

    function assignCompactPath(element, value) {
      element.textContent = compactPathValue(value);
      element.title = value || "";
    }

    function applyStatus(data) {
      const summary = data.summary;
      const action = data.last_action || {};

      els.statusPill.dataset.state = summary.state;
      els.statusPillText.textContent = summary.label;
      els.heroStack.textContent = summary.stack_line;
      els.heroStackSub.textContent = summary.stack_subline;
      els.heroTun.textContent = summary.tun_line;
      els.heroDns.textContent = summary.dns_line;
      els.heroLogs.textContent = summary.logs_line;
      els.heroLogsSub.textContent = summary.logs_subline;

      els.stateSummary.textContent = summary.description;
      els.runtimeMode.textContent = data.runtime.mode_label;
      els.xrayPid.textContent = data.processes.xray_pid || "—";
      els.singboxPid.textContent = data.processes.singbox_pid || "—";

      renderBadges(els.stateBadges, [
        badge(summary.badges[0], summary.state === "running" ? "success" : summary.state === "stopped" ? "danger" : "accent"),
        badge(summary.badges[1], data.processes.tun_present ? "success" : "danger"),
        badge(summary.badges[2], data.settings.file_logs_enabled ? "accent" : "")
      ]);

      els.remoteHost.textContent = data.connection.remote_endpoint || "—";
      els.remoteSni.textContent = data.connection.remote_sni || "—";
      els.localPorts.textContent = data.connection.local_ports || "—";
      els.tunAddress.textContent = data.connection.tun_address || "—";
      els.tunInterface.textContent = data.connection.tun_interface || "—";
      els.dnsServers.textContent = data.connection.dns_servers || "—";

      assignCompactPath(els.latestDiagnostic, data.artifacts.latest_diagnostic || "—");
      assignCompactPath(els.stateFile, data.artifacts.state_file || "—");
      assignCompactPath(els.resolvBackup, data.artifacts.resolv_backup || "—");
      assignCompactPath(els.logFiles, data.artifacts.log_files || "—");

      els.lastActionName.textContent = action.name || "—";
      els.lastActionTime.textContent = formatTimestamp(action.timestamp);
      els.lastActionMessage.textContent = action.message || "—";
      els.commandOutput.textContent = action.details || "Нет детального вывода.";

      const actionBadges = [];
      if (action.ok === true) actionBadges.push(badge("успех", "success"));
      if (action.ok === false) actionBadges.push(badge("ошибка", "danger"));
      if (data.runtime.requires_terminal_sudo_hint) actionBadges.push(badge("sudo может ждать подтверждение в терминале", "accent"));
      renderBadges(els.actionBadges, actionBadges);

      els.loggingToggle.checked = Boolean(data.settings.file_logs_enabled);

      els.startButton.disabled = state.busy || summary.state === "running";
      els.stopButton.disabled = state.busy || summary.state === "stopped";
    }

    async function fetchStatus() {
      const response = await fetch("/api/status", { cache: "no-store" });
      if (!response.ok) {
        throw new Error(`status ${response.status}`);
      }
      const data = await response.json();
      applyStatus(data);
    }

    async function runAction(endpoint) {
      setBusy(true);
      try {
        const response = await fetch(endpoint, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: "{}"
        });
        const data = await response.json();
        if (!response.ok) {
          throw new Error(data.message || `action ${response.status}`);
        }
        applyStatus(data.status);
      } catch (error) {
        els.lastActionMessage.textContent = `Ошибка: ${error.message}`;
      } finally {
        setBusy(false);
        await fetchStatus();
      }
    }

    async function saveLoggingSetting() {
      setBusy(true);
      try {
        const response = await fetch("/api/settings/logging", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ enabled: els.loggingToggle.checked })
        });
        const data = await response.json();
        if (!response.ok) {
          throw new Error(data.message || `settings ${response.status}`);
        }
        applyStatus(data.status);
      } catch (error) {
        els.loggingToggle.checked = !els.loggingToggle.checked;
        els.lastActionMessage.textContent = `Ошибка сохранения настройки: ${error.message}`;
      } finally {
        setBusy(false);
      }
    }

    els.startButton.addEventListener("click", () => runAction("/api/start"));
    els.stopButton.addEventListener("click", () => runAction("/api/stop"));
    els.diagButton.addEventListener("click", () => runAction("/api/diagnostics"));
    els.loggingToggle.addEventListener("change", saveLoggingSetting);

    fetchStatus().catch((error) => {
      els.lastActionMessage.textContent = `Не удалось получить состояние: ${error.message}`;
    });

    state.polling = window.setInterval(() => {
      if (!state.busy) {
        fetchStatus().catch(() => {});
      }
    }, 4000);
  </script>
</body>
</html>
"""


@dataclass
class CommandResult:
    name: str
    ok: bool
    returncode: int
    output: str


def iso_now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def read_json_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def write_json_file(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_settings() -> dict[str, Any]:
    raw = read_json_file(SETTINGS_FILE)
    return {
        "file_logs_enabled": bool(raw.get("file_logs_enabled", False)),
    }


def save_settings(file_logs_enabled: bool) -> None:
    SETTINGS_FILE.write_text(
        json.dumps({"file_logs_enabled": bool(file_logs_enabled)}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    SETTINGS_FILE.chmod(0o644)
    if os.geteuid() == 0:
        os.chown(SETTINGS_FILE, REAL_UID, REAL_GID)


def load_state_file() -> dict[str, str]:
    if not STATE_FILE.exists():
        return {}

    result: dict[str, str] = {}
    for line in STATE_FILE.read_text(encoding="utf-8").splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key.strip()] = value.strip()
    return result


def is_pid_alive(value: str | None) -> bool:
    if not value or not value.isdigit():
        return False
    return Path(f"/proc/{value}").exists()


def read_resolv_conf_nameservers() -> list[str]:
    resolv_path = Path("/etc/resolv.conf")
    if not resolv_path.exists():
        return []

    servers: list[str] = []
    for line in resolv_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if line.startswith("nameserver "):
            servers.append(line.split()[1])
    return servers


def load_xray_config() -> dict[str, Any]:
    try:
        return json.loads(XRAY_CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def load_singbox_config() -> dict[str, Any]:
    try:
        return json.loads(SINGBOX_CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def find_latest_diagnostic() -> Path | None:
    if not LOG_DIR.exists():
        return None
    candidates = sorted(LOG_DIR.glob("xray-tun-state-*.log"), key=lambda item: item.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None


def normalize_output(text: str, limit: int = 12000) -> str:
    cleaned = text.strip()
    if not cleaned:
        return "Команда не вернула текстовый вывод."
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[-limit:]


def remember_action(name: str, ok: bool | None, message: str, details: str) -> None:
    LAST_ACTION.update(
        {
            "name": name,
            "ok": ok,
            "message": message,
            "timestamp": iso_now(),
            "details": normalize_output(details),
        }
    )


def run_shell_action(name: str, script: Path, extra_env: dict[str, str] | None = None) -> CommandResult:
    env = os.environ.copy()
    env.update(
        {
            "SUDO_USER": REAL_USER,
            "USER": REAL_USER,
            "LOGNAME": REAL_USER,
            "HOME": str(REAL_HOME),
        }
    )
    env.update(extra_env or {})

    if os.geteuid() != 0:
        command = ["sudo", str(script)]
    else:
        command = [str(script)]

    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    output = "\n".join(part for part in [completed.stdout.strip(), completed.stderr.strip()] if part).strip()
    ok = completed.returncode == 0
    return CommandResult(name=name, ok=ok, returncode=completed.returncode, output=output)


def parse_connection_info() -> dict[str, str]:
    xray = load_xray_config()
    singbox = load_singbox_config()

    remote_endpoint = "—"
    remote_sni = "—"
    socks_port = "127.0.0.1:10808"
    mixed_port = "127.0.0.1:7897"
    tun_address = "—"

    try:
        proxy = next(outbound for outbound in xray.get("outbounds", []) if outbound.get("tag") == "proxy")
        vnext = proxy.get("settings", {}).get("vnext", [{}])[0]
        address = vnext.get("address")
        port = vnext.get("port")
        if address and port:
            remote_endpoint = f"{address}:{port}"
        remote_sni = proxy.get("streamSettings", {}).get("realitySettings", {}).get("serverName", "—")
    except StopIteration:
        pass

    try:
        inbound = next(item for item in xray.get("inbounds", []) if item.get("tag") == "socks-in")
        socks_port = f"{inbound.get('listen', '127.0.0.1')}:{inbound.get('port', 10808)}"
    except StopIteration:
        pass

    try:
        mixed_in = next(item for item in singbox.get("inbounds", []) if item.get("tag") == "mixed-in")
        mixed_port = f"{mixed_in.get('listen', '127.0.0.1')}:{mixed_in.get('listen_port', 7897)}"
    except StopIteration:
        pass

    try:
        tun_in = next(item for item in singbox.get("inbounds", []) if item.get("tag") == "tun-in")
        addresses = tun_in.get("address", [])
        if addresses:
            tun_address = ", ".join(addresses)
    except StopIteration:
        pass

    dns_servers = [
        f"{server.get('server')}:{server.get('server_port', 53)}"
        for server in singbox.get("dns", {}).get("servers", [])
        if server.get("server")
    ]

    return {
        "remote_endpoint": remote_endpoint,
        "remote_sni": remote_sni,
        "local_ports": f"SOCKS {socks_port} | MIXED {mixed_port}",
        "tun_address": tun_address,
        "tun_interface": "tun0",
        "dns_servers": ", ".join(dns_servers) if dns_servers else "—",
    }


def collect_status() -> dict[str, Any]:
    settings = load_settings()
    state = load_state_file()

    xray_pid = state.get("XRAY_PID")
    singbox_pid = state.get("SINGBOX_PID")
    xray_alive = is_pid_alive(xray_pid)
    singbox_alive = is_pid_alive(singbox_pid)
    tun_present = Path("/sys/class/net/tun0").exists()

    if xray_alive and singbox_alive and tun_present:
        state_key = "running"
        state_label = "Подключение активно"
        description = "Xray, sing-box и tun0 активны."
    elif xray_alive or singbox_alive or tun_present:
        state_key = "degraded"
        state_label = "Состояние частичное"
        description = "Часть стека активна, стоит снять диагностику."
    else:
        state_key = "stopped"
        state_label = "Стек остановлен"
        description = "Процессы остановлены, tun0 не поднят."

    dns_runtime = ", ".join(read_resolv_conf_nameservers()) or "DNS не прочитан"
    latest_diag = find_latest_diagnostic()
    runtime_mode = "root-server" if os.geteuid() == 0 else "user-server"
    runtime_label = (
        "Root-backend через pkexec."
        if os.geteuid() == 0
        else "Пользовательский backend; возможен запрос sudo в терминале."
    )

    log_files = []
    for candidate in [LOG_DIR / "xray-subvost.log", LOG_DIR / "singbox-subvost.log"]:
        if candidate.exists():
            log_files.append(str(candidate))

    return {
        "summary": {
            "state": state_key,
            "label": state_label,
            "description": description,
            "stack_line": "Xray + sing-box",
            "stack_subline": "Через существующие bundle-скрипты",
            "tun_line": "tun0 готов" if tun_present else "tun0 отсутствует",
            "dns_line": dns_runtime,
            "logs_line": "Файловые логи включены" if settings["file_logs_enabled"] else "Файловые логи выключены",
            "logs_subline": "Применяется при следующем старте",
            "badges": [
                state_label,
                "tun0 найден" if tun_present else "tun0 не найден",
                "логирование включено" if settings["file_logs_enabled"] else "логирование выключено",
            ],
        },
        "settings": settings,
        "processes": {
            "xray_pid": xray_pid if xray_alive else None,
            "singbox_pid": singbox_pid if singbox_alive else None,
            "xray_alive": xray_alive,
            "singbox_alive": singbox_alive,
            "tun_present": tun_present,
        },
        "connection": {
            **parse_connection_info(),
            "dns_servers": dns_runtime,
        },
        "runtime": {
            "mode": runtime_mode,
            "mode_label": runtime_label,
            "requires_terminal_sudo_hint": os.geteuid() != 0,
        },
        "artifacts": {
            "latest_diagnostic": str(latest_diag) if latest_diag else None,
            "state_file": str(STATE_FILE),
            "resolv_backup": str(RESOLV_BACKUP),
            "log_files": ", ".join(log_files) if log_files else "Логи ещё не созданы",
        },
        "bundle_identity": {
            "project_root": str(PROJECT_ROOT),
        },
        "project_root": str(PROJECT_ROOT),
        "gui_version": GUI_VERSION,
        "last_action": LAST_ACTION.copy(),
        "timestamp": iso_now(),
    }


def handle_start() -> dict[str, Any]:
    settings = load_settings()
    env = {"ENABLE_FILE_LOGS": "1" if settings["file_logs_enabled"] else "0"}
    result = run_shell_action("Старт", RUN_SCRIPT, env)
    if result.ok:
        message = "Запуск завершён успешно."
    else:
        message = f"Запуск завершился ошибкой, код {result.returncode}."
    remember_action(result.name, result.ok, message, result.output)
    return collect_status()


def handle_stop() -> dict[str, Any]:
    result = run_shell_action("Стоп", STOP_SCRIPT)
    if result.ok:
        message = "Остановка выполнена."
    else:
        message = f"Остановка завершилась ошибкой, код {result.returncode}."
    remember_action(result.name, result.ok, message, result.output)
    return collect_status()


def handle_diagnostics() -> dict[str, Any]:
    result = run_shell_action("Диагностика", DIAG_SCRIPT)
    match = re.search(r"(/.+xray-tun-state-[^\\s]+\\.log)", result.output)
    if result.ok and match:
        message = f"Диагностика сохранена в {match.group(1)}."
    elif result.ok:
        message = "Диагностика снята."
    else:
        message = f"Диагностика завершилась ошибкой, код {result.returncode}."
    remember_action(result.name, result.ok, message, result.output)
    return collect_status()


class Handler(BaseHTTPRequestHandler):
    server_version = "SubvostGui/1.0"

    def log_message(self, format: str, *args: Any) -> None:
        return

    def send_json(self, payload: dict[str, Any], status: int = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def send_html(self, body: str) -> None:
        data = body.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        if not raw:
            return {}
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return {}

    def do_GET(self) -> None:
        if self.path in ["/", "/index.html"]:
            self.send_html(INDEX_HTML)
            return

        if self.path == "/api/status":
            self.send_json(collect_status())
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def do_POST(self) -> None:
        if self.path == "/api/settings/logging":
            payload = self.read_json_body()
            enabled = bool(payload.get("enabled"))
            save_settings(enabled)
            remember_action(
                "Настройки",
                True,
                "Режим файлового логирования сохранён.",
                f"file_logs_enabled={int(enabled)}",
            )
            self.send_json({"ok": True, "status": collect_status()})
            return

        if self.path not in ["/api/start", "/api/stop", "/api/diagnostics"]:
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")
            return

        if not ACTION_LOCK.acquire(blocking=False):
            self.send_json(
                {
                    "ok": False,
                    "message": "Другая операция ещё выполняется. Дождитесь завершения.",
                    "status": collect_status(),
                },
                status=HTTPStatus.CONFLICT,
            )
            return

        try:
            if self.path == "/api/start":
                status = handle_start()
            elif self.path == "/api/stop":
                status = handle_stop()
            else:
                status = handle_diagnostics()
        finally:
            ACTION_LOCK.release()

        self.send_json({"ok": True, "status": status})


def main() -> None:
    parser = argparse.ArgumentParser(description="Локальный GUI для управления Subvost Xray TUN bundle.")
    parser.add_argument("--host", default=DEFAULT_HOST, help=f"Адрес для HTTP сервера. По умолчанию {DEFAULT_HOST}.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"Порт для HTTP сервера. По умолчанию {DEFAULT_PORT}.")
    args = parser.parse_args()

    remember_action(
        "Инициализация",
        True,
        f"GUI backend запущен для пользователя {REAL_USER}. Откройте http://{args.host}:{args.port}",
        "Сервер готов к работе.",
    )

    with ThreadingHTTPServer((args.host, args.port), Handler) as httpd:
        print(f"Subvost GUI доступен: http://{args.host}:{args.port}")
        print(f"Корень bundle: {PROJECT_ROOT}")
        print(f"Реальный пользователь: {REAL_USER}")
        print(f"Файл настроек GUI: {SETTINGS_FILE}")
        print("Для остановки нажмите Ctrl+C")
        httpd.serve_forever()


if __name__ == "__main__":
    main()
