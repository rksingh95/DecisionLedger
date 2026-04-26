"""
DAI Server — EU AI Act Article 19 PDF Renderer
================================================

Generates a professional PDF compliance report from an Article19Export.

Requires: reportlab (install with: pip install decision-ledger-sdk[server])
"""

from __future__ import annotations

import io
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dai_server.export.article19 import Article19Export

# ── Design tokens ─────────────────────────────────────────────────────────────
_BRAND_DARK = (0.05, 0.08, 0.18)  # near-black navy
_BRAND_BLUE = (0.09, 0.35, 0.75)  # primary accent blue
_BRAND_TEAL = (0.11, 0.65, 0.62)  # secondary teal
_BRAND_LIGHT = (0.95, 0.97, 1.00)  # very light blue-white (backgrounds)
_BRAND_MID = (0.80, 0.87, 0.96)  # mid-tone blue for alternating rows
_TEXT_BODY = (0.15, 0.15, 0.20)  # body text
_TEXT_MUTED = (0.45, 0.48, 0.55)  # muted / captions
_SUCCESS = (0.13, 0.60, 0.34)  # green for PASS
_DANGER = (0.82, 0.20, 0.22)  # red for FAIL
_WARNING = (0.85, 0.52, 0.09)  # amber for exceptions/overrides


def _rgb(*args: tuple[float, float, float]) -> tuple[float, float, float]:
    return args[0]


def generate_article19_pdf(export: Article19Export) -> bytes:
    """
    Render an Article 19 compliance report as a professional PDF.

    Args:
        export: The populated Article19Export dataclass.

    Returns:
        PDF bytes ready to stream as a response or write to disk.
    """
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.units import cm, mm
        from reportlab.platypus import (
            HRFlowable,
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )
    except ImportError as exc:
        raise RuntimeError(
            "reportlab is required to generate PDF exports. Install with: pip install reportlab"
        ) from exc

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2.5 * cm,
        bottomMargin=2.5 * cm,
        title="EU AI Act Article 19 — Decision Ledger Compliance Report",
        author="DecisionLedger SDK",
        subject="Automated AI Decision Audit Log",
    )

    page_w = A4[0] - 4 * cm  # usable width

    # ── Custom styles ──────────────────────────────────────────────────────────
    def brand_color(rgb: tuple[float, float, float]) -> colors.Color:
        return colors.Color(*rgb)

    S = {
        "cover_title": ParagraphStyle(
            "cover_title",
            fontSize=26,
            leading=32,
            fontName="Helvetica-Bold",
            textColor=brand_color(_BRAND_DARK),
            spaceAfter=4 * mm,
        ),
        "cover_sub": ParagraphStyle(
            "cover_sub",
            fontSize=12,
            leading=16,
            fontName="Helvetica",
            textColor=brand_color(_BRAND_BLUE),
            spaceAfter=2 * mm,
        ),
        "cover_meta": ParagraphStyle(
            "cover_meta",
            fontSize=9,
            leading=13,
            fontName="Helvetica",
            textColor=brand_color(_TEXT_MUTED),
        ),
        "section_heading": ParagraphStyle(
            "section_heading",
            fontSize=13,
            leading=18,
            fontName="Helvetica-Bold",
            textColor=brand_color(_BRAND_DARK),
            spaceBefore=6 * mm,
            spaceAfter=3 * mm,
        ),
        "body": ParagraphStyle(
            "body",
            fontSize=9,
            leading=13,
            fontName="Helvetica",
            textColor=brand_color(_TEXT_BODY),
        ),
        "body_bold": ParagraphStyle(
            "body_bold",
            fontSize=9,
            leading=13,
            fontName="Helvetica-Bold",
            textColor=brand_color(_TEXT_BODY),
        ),
        "caption": ParagraphStyle(
            "caption",
            fontSize=8,
            leading=11,
            fontName="Helvetica-Oblique",
            textColor=brand_color(_TEXT_MUTED),
            spaceAfter=2 * mm,
        ),
        "badge_pass": ParagraphStyle(
            "badge_pass",
            fontSize=9,
            fontName="Helvetica-Bold",
            textColor=brand_color(_SUCCESS),
        ),
        "badge_fail": ParagraphStyle(
            "badge_fail",
            fontSize=9,
            fontName="Helvetica-Bold",
            textColor=brand_color(_DANGER),
        ),
        "record_id": ParagraphStyle(
            "record_id",
            fontSize=7.5,
            fontName="Courier",
            textColor=brand_color(_BRAND_BLUE),
        ),
        "record_body": ParagraphStyle(
            "record_body",
            fontSize=8,
            leading=11,
            fontName="Helvetica",
            textColor=brand_color(_TEXT_BODY),
        ),
        "warning_text": ParagraphStyle(
            "warning_text",
            fontSize=8,
            leading=11,
            fontName="Helvetica-BoldOblique",
            textColor=brand_color(_WARNING),
        ),
    }

    def hr(color: tuple[float, float, float] = _BRAND_BLUE, width: float = 0.75) -> HRFlowable:
        return HRFlowable(width="100%", thickness=width, color=brand_color(color))

    def sp(h: float = 4.0) -> Spacer:
        return Spacer(1, h * mm)

    def heading(text: str) -> list:
        return [sp(6), Paragraph(text.upper(), S["section_heading"]), hr(_BRAND_TEAL, 0.5), sp(2)]

    story: list = []

    # ══════════════════════════════════════════════════════════════════════════
    # COVER
    # ══════════════════════════════════════════════════════════════════════════
    chain_ok = export.chain_integrity_valid
    chain_label = "✓  CHAIN INTEGRITY VERIFIED" if chain_ok else "✗  CHAIN INTEGRITY BROKEN"
    chain_style = S["badge_pass"] if chain_ok else S["badge_fail"]

    story += [
        sp(8),
        Paragraph("EU AI Act — Article 19", S["cover_sub"]),
        Paragraph("AI Decision Ledger<br/>Compliance Report", S["cover_title"]),
        sp(3),
        hr(_BRAND_BLUE, 1.5),
        sp(3),
    ]

    # Meta grid (2-column)
    meta = [
        [
            "Reporting Period",
            f"{export.period_from.strftime('%Y-%m-%d %H:%M UTC')}  →  {export.period_to.strftime('%Y-%m-%d %H:%M UTC')}",
        ],
        ["Generated At", export.generated_at.strftime("%Y-%m-%d %H:%M:%S UTC")],
        ["Ledger Version", str(export.ledger_version)],
        ["Total Decisions", str(export.total_decisions)],
        ["Unique Agents", str(len(export.decisions_by_agent))],
    ]
    meta_table = Table(
        [[Paragraph(k, S["body_bold"]), Paragraph(v, S["body"])] for k, v in meta],
        colWidths=[page_w * 0.32, page_w * 0.68],
    )
    meta_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), brand_color(_BRAND_LIGHT)),
                (
                    "ROWBACKGROUNDS",
                    (0, 0),
                    (-1, -1),
                    [brand_color(_BRAND_LIGHT), brand_color(_BRAND_MID)],
                ),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("GRID", (0, 0), (-1, -1), 0.25, brand_color(_BRAND_MID)),
                ("ROUNDEDCORNERS", [4, 4, 4, 4]),
            ]
        )
    )
    story += [meta_table, sp(4), Paragraph(chain_label, chain_style), sp(8)]

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 1 — EXECUTIVE SUMMARY
    # ══════════════════════════════════════════════════════════════════════════
    story += heading("1. Executive Summary")

    # KPI strip
    kpis = [
        ("Decisions", str(export.total_decisions), _BRAND_BLUE),
        (
            "Exceptions",
            str(export.exception_count),
            _WARNING if export.exception_count else _SUCCESS,
        ),
        ("Overrides", str(export.override_count), _WARNING if export.override_count else _SUCCESS),
        ("Chain OK", "YES" if chain_ok else "NO", _SUCCESS if chain_ok else _DANGER),
    ]

    kpi_table = Table(
        [
            [Paragraph(label, S["caption"]) for label, *_ in kpis],
            [
                Paragraph(
                    val,
                    ParagraphStyle(
                        f"kpiv_{i}",
                        fontSize=18,
                        fontName="Helvetica-Bold",
                        textColor=brand_color(col),
                        leading=22,
                    ),
                )
                for i, (_, val, col) in enumerate(kpis)
            ],
        ],
        colWidths=[page_w / 4] * 4,
    )
    kpi_table.setStyle(
        TableStyle(
            [
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BACKGROUND", (0, 0), (-1, -1), brand_color(_BRAND_LIGHT)),
                ("BOX", (0, 0), (-1, -1), 0.5, brand_color(_BRAND_MID)),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LINEBEFORE", (1, 0), (-1, -1), 0.5, brand_color(_BRAND_MID)),
            ]
        )
    )
    story += [kpi_table, sp(4)]

    # Outcomes table
    story += [Paragraph("Outcome Distribution", S["body_bold"]), sp(2)]
    outcome_rows = [["Outcome", "Count", "% of Total"]]
    for outcome, count in sorted(export.outcomes_summary.items()):
        pct = f"{count / export.total_decisions * 100:.1f}%" if export.total_decisions else "—"
        outcome_rows.append([outcome.title(), str(count), pct])
    outcome_table = Table(outcome_rows, colWidths=[page_w * 0.5, page_w * 0.25, page_w * 0.25])
    outcome_table.setStyle(_std_table_style(brand_color))
    story += [outcome_table, sp(4)]

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 2 — AGENT ACTIVITY
    # ══════════════════════════════════════════════════════════════════════════
    story += heading("2. Agent Activity")
    agent_rows = [["Agent ID", "Decisions", "% of Total"]]
    for agent, count in sorted(export.decisions_by_agent.items(), key=lambda x: -x[1]):
        pct = f"{count / export.total_decisions * 100:.1f}%" if export.total_decisions else "—"
        agent_rows.append([agent, str(count), pct])
    agent_table = Table(agent_rows, colWidths=[page_w * 0.55, page_w * 0.25, page_w * 0.20])
    agent_table.setStyle(_std_table_style(brand_color))
    story.append(agent_table)

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 3 — DECISION TYPES
    # ══════════════════════════════════════════════════════════════════════════
    story += heading("3. Decision Types")
    dtype_rows = [["Decision Type", "Count"]]
    for dtype, count in sorted(export.decisions_by_type.items(), key=lambda x: -x[1]):
        dtype_rows.append([dtype.replace("_", " ").title(), str(count)])
    dtype_table = Table(dtype_rows, colWidths=[page_w * 0.75, page_w * 0.25])
    dtype_table.setStyle(_std_table_style(brand_color))
    story.append(dtype_table)

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 4 — POLICY VERSIONS
    # ══════════════════════════════════════════════════════════════════════════
    story += heading("4. Policy Versions Used")
    policy_rows = [["Policy Version"]]
    for pv in export.policy_versions_used:
        policy_rows.append([pv])
    policy_table = Table(policy_rows, colWidths=[page_w])
    policy_table.setStyle(_std_table_style(brand_color))
    story.append(policy_table)

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 5 — EXCEPTIONS & OVERRIDES
    # ══════════════════════════════════════════════════════════════════════════
    if export.exception_count or export.override_count:
        story += heading("5. Exceptions & Overrides")
        flagged_records = [r for r in export.records if r.exception_applied or r.override_applied]
        exc_rows = [["Decision ID", "Timestamp", "Type", "Agent", "Flag", "Reason"]]
        for r in flagged_records:
            flag = []
            if r.exception_applied:
                flag.append(f"EXCEPTION ({r.exception_type.value if r.exception_type else '—'})")
            if r.override_applied:
                flag.append(f"OVERRIDE by {r.override_by or '—'}")
            exc_rows.append(
                [
                    Paragraph(r.decision_id[:16] + "…", S["record_id"]),
                    r.decision_timestamp.strftime("%Y-%m-%d %H:%M"),
                    r.decision_type.replace("_", "\n"),
                    r.agent_id,
                    Paragraph("\n".join(flag), S["warning_text"]),
                    Paragraph(
                        r.exception_reason_code or r.override_justification or "—", S["record_body"]
                    ),
                ]
            )
        exc_table = Table(
            exc_rows,
            colWidths=[
                page_w * 0.14,
                page_w * 0.13,
                page_w * 0.16,
                page_w * 0.18,
                page_w * 0.19,
                page_w * 0.20,
            ],
        )
        exc_table.setStyle(_std_table_style(brand_color, header_bg=_DANGER))
        story.append(exc_table)
    else:
        story += heading("5. Exceptions & Overrides")
        story.append(Paragraph("No exceptions or overrides recorded in this period.", S["body"]))

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 6 — CHAIN INTEGRITY
    # ══════════════════════════════════════════════════════════════════════════
    story += heading("6. Chain Integrity Verification")
    integrity_rows = [
        ["Verification Status", "PASSED ✓" if chain_ok else "FAILED ✗"],
        ["Total Records Verified", str(export.total_decisions)],
        ["Broken At (if any)", export.chain_integrity_broken_at or "N/A"],
        ["Verification Method", "SHA-256 hash chain (each record includes previous record hash)"],
    ]
    int_table = Table(
        [
            [
                Paragraph(k, S["body_bold"]),
                Paragraph(
                    v,
                    S["badge_pass"]
                    if (k == "Verification Status" and chain_ok)
                    else S["badge_fail"]
                    if k == "Verification Status"
                    else S["body"],
                ),
            ]
            for k, v in integrity_rows
        ],
        colWidths=[page_w * 0.35, page_w * 0.65],
    )
    int_table.setStyle(_std_table_style(brand_color))
    story.append(int_table)

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 7 — INDIVIDUAL RECORDS
    # ══════════════════════════════════════════════════════════════════════════
    story += heading("7. Individual Decision Records")
    story.append(
        Paragraph(
            f"All {export.total_decisions} decision records in this reporting period, "
            "ordered by timestamp. Each record is cryptographically linked to the previous.",
            S["caption"],
        )
    )
    story.append(sp(2))

    rec_rows = [["#", "Timestamp", "Decision ID", "Type", "Agent", "Outcome", "Conf.", "Flags"]]
    for i, r in enumerate(export.records, 1):
        flags = []
        if r.exception_applied:
            flags.append("EXC")
        if r.override_applied:
            flags.append("OVR")
        flag_text = ", ".join(flags) if flags else "—"
        rec_rows.append(
            [
                str(i),
                r.decision_timestamp.strftime("%m-%d\n%H:%M"),
                Paragraph(r.decision_id[:14] + "…", S["record_id"]),
                r.decision_type.replace("_", "\n"),
                r.agent_id.split("-")[0] + "…",
                r.outcome.title(),
                f"{r.confidence:.0%}",
                Paragraph(flag_text, S["warning_text"] if flags else S["body"]),
            ]
        )

    rec_table = Table(
        rec_rows,
        colWidths=[
            page_w * 0.05,
            page_w * 0.10,
            page_w * 0.16,
            page_w * 0.18,
            page_w * 0.18,
            page_w * 0.12,
            page_w * 0.08,
            page_w * 0.13,
        ],
        repeatRows=1,
    )
    rec_table.setStyle(_std_table_style(brand_color, alternating=True))
    story.append(rec_table)

    # ══════════════════════════════════════════════════════════════════════════
    # FOOTER NOTE
    # ══════════════════════════════════════════════════════════════════════════
    story += [
        sp(8),
        hr(_BRAND_TEAL, 0.5),
        sp(2),
        Paragraph(
            "This report is automatically generated by <b>DecisionLedger SDK</b> "
            "and satisfies EU AI Act Article 19 logging requirements for high-risk AI systems. "
            "The cryptographic hash chain provides tamper-evidence for all records. "
            f"Report generated: {export.generated_at.strftime('%Y-%m-%d %H:%M:%S UTC')}.",
            S["caption"],
        ),
    ]

    doc.build(story)
    return buf.getvalue()


def _std_table_style(brand_color_fn, header_bg=None, alternating: bool = False):
    """Return a standard branded TableStyle."""
    from reportlab.platypus import TableStyle

    hdr_bg = header_bg if header_bg is not None else _BRAND_BLUE
    cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), brand_color_fn(hdr_bg)),
        ("TEXTCOLOR", (0, 0), (-1, 0), brand_color_fn((1, 1, 1))),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.3, brand_color_fn(_BRAND_MID)),
        (
            "ROWBACKGROUNDS",
            (0, 1),
            (-1, -1),
            [brand_color_fn(_BRAND_LIGHT), brand_color_fn((1, 1, 1))]
            if alternating
            else [brand_color_fn((1, 1, 1))],
        ),
    ]
    return TableStyle(cmds)
