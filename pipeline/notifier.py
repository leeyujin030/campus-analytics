"""알림 모듈 — macOS 팝업 + 이메일 발송 + 로그 기록"""
from __future__ import annotations

import logging
import os
import smtplib
import subprocess
from datetime import datetime
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path


def _setup_logger(log_dir: Path, date_label: str) -> logging.Logger:
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{date_label}.log"

    logger = logging.getLogger(f"campus_analytics.{date_label}")
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        logger.addHandler(fh)

    return logger


def notify_success(
    date_label: str,
    report_path: Path,
    kpi: dict,
    unmapped_count: int,
    log_dir: Path,
):
    logger = _setup_logger(log_dir, date_label)
    total = f"{kpi['총_결제금액']:,}"
    orders = f"{kpi['총_주문건수']:,}"
    msg = f"캠퍼스 데일리 리포트 완료 ({date_label})\n총 결제금액: {total}원 | 주문: {orders}건"
    if unmapped_count:
        msg += f"\n⚠️ 미분류 가맹점 {unmapped_count}개 — 업종 매핑 확인 필요"
    _mac_popup(msg, title="캠퍼스 애널리틱스", subtitle=str(report_path.name))
    logger.info("리포트 생성 완료: %s | 총결제 %s원 | 주문 %s건 | 미분류 %d개",
                report_path.name, total, orders, unmapped_count)


def notify_error(date_label: str, error: Exception, log_dir: Path):
    logger = _setup_logger(log_dir, date_label)
    msg = f"캠퍼스 데일리 리포트 실패\n{type(error).__name__}: {error}"
    _mac_popup(msg, title="캠퍼스 애널리틱스 오류")
    logger.error("파이프라인 오류: %s", error, exc_info=True)


def _mac_popup(message: str, title: str = "캠퍼스 애널리틱스", subtitle: str = ""):
    subtitle_part = f'subtitle "{subtitle}"' if subtitle else ""
    script = (
        f'display notification "{message}" '
        f'with title "{title}" {subtitle_part}'
    )
    try:
        subprocess.run(["osascript", "-e", script], check=False, timeout=5)
    except Exception:
        pass


def send_email(
    report_path: Path,
    date_label: str,
    kpi: dict,
    cfg: dict,
    log_dir: Path,
):
    """SMTP 이메일 발송 (config.yaml email 섹션 사용)"""
    logger = _setup_logger(log_dir, date_label)

    password = os.environ.get("CAMPUS_SMTP_PASSWORD", "")
    if not password:
        logger.warning("CAMPUS_SMTP_PASSWORD 미설정 — 이메일 발송 건너뜀")
        return

    recipients = cfg.get("to", [])
    if not recipients:
        logger.warning("수신자 목록 비어있음 — 이메일 발송 건너뜀")
        return

    sender = cfg["from"]
    subject = f"[캠퍼스 애널리틱스] {date_label} 일별 리포트"

    total = f"{kpi['총_결제금액']:,}"
    orders = f"{kpi['총_주문건수']:,}"
    body = (
        f"안녕하세요,\n\n"
        f"{date_label} 캠퍼스 데일리 리포트를 첨부합니다.\n\n"
        f"- 총 결제금액: {total}원\n"
        f"- 총 주문건수: {orders}건\n"
        f"- 캠퍼스 수: {kpi['캠퍼스_수']}개\n"
        f"- 가맹점 수: {kpi['가맹점_수']}개\n\n"
        f"NHN Payco 캠퍼스 사업팀\n"
        f"캠퍼스 데일리 애널리틱스 자동발송"
    )

    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    with open(report_path, "rb") as f:
        att = MIMEApplication(f.read(), Name=report_path.name)
    att["Content-Disposition"] = f'attachment; filename="{report_path.name}"'
    msg.attach(att)

    host = cfg.get("smtp_host", "smtp.gmail.com")
    port = cfg.get("smtp_port", 587)

    try:
        with smtplib.SMTP(host, port, timeout=30) as server:
            server.starttls()
            server.login(sender, password)
            server.sendmail(sender, recipients, msg.as_string())
        logger.info("이메일 발송 완료 → %s", recipients)
    except Exception as e:
        logger.error("이메일 발송 실패: %s", e)
        raise
