"""
DAI Server — EU AI Act Article 19 Export
==========================================

Generates compliance exports covering the Article 19 logging requirements
of the EU AI Act for high-risk AI systems.
"""

import json
from dataclasses import dataclass
from datetime import UTC, datetime

from dai.models import ChainVerifyResult, DecisionRecord


@dataclass
class Article19Export:
    """Structured Article 19 compliance export."""

    period_from: datetime
    period_to: datetime
    total_decisions: int
    decisions_by_type: dict[str, int]
    decisions_by_agent: dict[str, int]
    outcomes_summary: dict[str, int]
    exception_count: int
    override_count: int
    chain_integrity_valid: bool
    chain_integrity_broken_at: str | None
    policy_versions_used: list[str]
    generated_at: datetime
    ledger_version: str
    records: list[DecisionRecord]

    def to_json(self) -> str:
        """Machine-readable JSON export."""
        data = {
            "period_from": self.period_from.isoformat(),
            "period_to": self.period_to.isoformat(),
            "total_decisions": self.total_decisions,
            "decisions_by_type": self.decisions_by_type,
            "decisions_by_agent": self.decisions_by_agent,
            "outcomes_summary": self.outcomes_summary,
            "exception_count": self.exception_count,
            "override_count": self.override_count,
            "chain_integrity_valid": self.chain_integrity_valid,
            "chain_integrity_broken_at": self.chain_integrity_broken_at,
            "policy_versions_used": self.policy_versions_used,
            "generated_at": self.generated_at.isoformat(),
            "ledger_version": self.ledger_version,
            "records": [r.to_audit_dict() for r in self.records],
        }
        return json.dumps(data, indent=2, default=str)

    def to_text_report(self) -> str:
        """Human-readable plain text compliance report."""
        chain_status = (
            "VERIFIED"
            if self.chain_integrity_valid
            else f"BROKEN at decision {self.chain_integrity_broken_at}"
        )
        lines: list[str] = [
            "═══════════════════════════════════════════════════════",
            "DECISION AUTHORITY INFRASTRUCTURE",
            "EU AI Act Article 19 Compliance Export",
            "═══════════════════════════════════════════════════════",
            "",
            f"Report Period: {self.period_from.strftime('%Y-%m-%d %H:%M UTC')} "
            f"to {self.period_to.strftime('%Y-%m-%d %H:%M UTC')}",
            f"Generated:     {self.generated_at.strftime('%Y-%m-%d %H:%M:%S UTC')}",
            f"Ledger Version: {self.ledger_version}",
            "",
            "SUMMARY",
            "─────────────────────────────────────────",
            f"Total decisions recorded:    {self.total_decisions}",
            f"Exception decisions:         {self.exception_count}",
            f"Human override decisions:    {self.override_count}",
            f"Chain integrity verified:    {'YES' if self.chain_integrity_valid else 'NO'}",
            "",
            "DECISIONS BY TYPE",
            "─────────────────────────────────────────",
        ]
        for dt, count in sorted(self.decisions_by_type.items()):
            lines.append(f"  {dt}: {count}")

        lines += [
            "",
            "DECISIONS BY AGENT",
            "─────────────────────────────────────────",
        ]
        for agent, count in sorted(self.decisions_by_agent.items()):
            lines.append(f"  {agent}: {count}")

        lines += [
            "",
            "OUTCOME DISTRIBUTION",
            "─────────────────────────────────────────",
        ]
        for outcome, count in sorted(self.outcomes_summary.items()):
            lines.append(f"  {outcome}: {count}")

        lines += [
            "",
            "POLICY VERSIONS IN USE",
            "─────────────────────────────────────────",
        ]
        for pv in sorted(self.policy_versions_used):
            lines.append(f"  {pv}")

        lines += [
            "",
            "CHAIN INTEGRITY",
            "─────────────────────────────────────────",
            f"Status: {chain_status}",
            f"Total records verified: {self.total_decisions}",
            "",
            "INDIVIDUAL RECORDS",
            "─────────────────────────────────────────",
        ]
        for r in self.records:
            lines.append(
                f"  [{r.decision_timestamp.strftime('%Y-%m-%d %H:%M:%S')}] "
                f"{r.decision_id[:8]}… | {r.decision_type} | {r.outcome} "
                f"({r.confidence:.2f}) | agent={r.agent_id}"
            )

        return "\n".join(lines)


def generate_article19_export(
    records: list[DecisionRecord],
    from_ts: datetime,
    to_ts: datetime,
    chain_result: ChainVerifyResult,
) -> Article19Export:
    """
    Generate an Article 19 compliance export from a list of decision records.

    Args:
        records: Decision records in the reporting period.
        from_ts: Start of the reporting period.
        to_ts: End of the reporting period.
        chain_result: Pre-computed chain verification result.

    Returns:
        Article19Export with aggregated statistics and full record list.
    """
    decisions_by_type: dict[str, int] = {}
    decisions_by_agent: dict[str, int] = {}
    outcomes_summary: dict[str, int] = {}
    policy_versions: set[str] = set()
    exception_count = 0
    override_count = 0

    for r in records:
        decisions_by_type[r.decision_type] = decisions_by_type.get(r.decision_type, 0) + 1
        decisions_by_agent[r.agent_id] = decisions_by_agent.get(r.agent_id, 0) + 1
        outcomes_summary[r.outcome] = outcomes_summary.get(r.outcome, 0) + 1
        policy_versions.add(f"{r.policy_id} v{r.policy_version}")
        if r.exception_applied:
            exception_count += 1
        if r.override_applied:
            override_count += 1

    from dai.models import LEDGER_VERSION

    return Article19Export(
        period_from=from_ts,
        period_to=to_ts,
        total_decisions=len(records),
        decisions_by_type=decisions_by_type,
        decisions_by_agent=decisions_by_agent,
        outcomes_summary=outcomes_summary,
        exception_count=exception_count,
        override_count=override_count,
        chain_integrity_valid=chain_result.valid,
        chain_integrity_broken_at=chain_result.broken_at,
        policy_versions_used=sorted(policy_versions),
        generated_at=datetime.now(UTC),
        ledger_version=LEDGER_VERSION,
        records=records,
    )
