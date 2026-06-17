"""Migration report generator - produces detailed reports of the migration process."""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..analyzer.accuracy_analyzer import AccuracyReport
from ..converter.code_converter import ConversionResult


class MigrationReporter:
    """Generates migration progress and final reports."""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_iteration_report(
        self,
        iteration: int,
        accuracy_report: AccuracyReport,
        conversion_result: ConversionResult,
    ) -> str:
        """Generate a report for a single iteration."""
        report_lines = [
            f"{'='*60}",
            f"  ITERATION {iteration} REPORT",
            f"{'='*60}",
            f"  Average Score: {accuracy_report.overall_score:.1f}%",
            f"  Lowest Dimension: {accuracy_report.min_dimension_score:.1f}%",
            f"  Dimensions Passed: {sum(1 for d in accuracy_report.dimensions if d.passed)}/{len(accuracy_report.dimensions)}",
            f"  Files Generated: {len(conversion_result.files)}",
            f"  Tokens Used: {conversion_result.tokens_used}",
            f"{'='*60}",
            "",
            "  DIMENSION SCORES (each must be >= threshold):",
            f"  {'-'*50}",
        ]

        for dim in accuracy_report.dimensions:
            bar = self._progress_bar(dim.score)
            status = "✓" if dim.passed else "✗"
            report_lines.append(
                f"  {status} {dim.name:<25} {bar} {dim.score:.1f}% (min: {dim.threshold:.0f}%)"
            )

        if accuracy_report.all_missing_items:
            report_lines.append(f"\n  MISSING ITEMS ({len(accuracy_report.all_missing_items)}):")
            for item in accuracy_report.all_missing_items[:20]:
                report_lines.append(f"    ✗ {item}")
            if len(accuracy_report.all_missing_items) > 20:
                report_lines.append(
                    f"    ... and {len(accuracy_report.all_missing_items) - 20} more"
                )

        if accuracy_report.all_incorrect_items:
            report_lines.append(f"\n  INCORRECT ITEMS ({len(accuracy_report.all_incorrect_items)}):")
            for item in accuracy_report.all_incorrect_items[:10]:
                report_lines.append(f"    ⚠ {item}")

        report_lines.append(f"\n  Summary: {accuracy_report.summary}")
        report_lines.append(f"{'='*60}\n")

        return '\n'.join(report_lines)

    def generate_final_report(
        self,
        program_id: str,
        iterations: list[tuple[int, AccuracyReport]],
        final_result: ConversionResult,
        total_tokens: int,
        elapsed_time: float,
    ) -> str:
        """Generate the final migration summary report."""
        final_report_data = iterations[-1][1] if iterations else None
        all_passed = final_report_data.all_dimensions_passed if final_report_data else False
        
        report_lines = [
            f"\n{'='*60}",
            f"  MIGRATION {'COMPLETE' if all_passed else 'FINISHED'} - FINAL REPORT",
            f"{'='*60}",
            f"  Program: {program_id}",
            f"  Status: {'✅ ALL DIMENSIONS PASSED' if all_passed else '⚠️  SOME DIMENSIONS BELOW THRESHOLD'}",
            f"  Average Score: {final_report_data.overall_score:.1f}%" if final_report_data else "",
            f"  Lowest Dimension: {final_report_data.min_dimension_score:.1f}%" if final_report_data else "",
            f"  Total Iterations: {len(iterations)}",
            f"  Total Tokens Used: {total_tokens:,}",
            f"  Elapsed Time: {elapsed_time:.1f}s",
            f"  Files Generated: {len(final_result.files)}",
            f"{'='*60}",
            "",
            "  ACCURACY PROGRESSION (lowest dimension per iteration):",
        ]

        for iteration, report in iterations:
            bar = self._progress_bar(report.min_dimension_score)
            passed = sum(1 for d in report.dimensions if d.passed)
            total = len(report.dimensions)
            report_lines.append(
                f"    Iteration {iteration}: {bar} min={report.min_dimension_score:.1f}% "
                f"({passed}/{total} passed)"
            )

        report_lines.append(f"\n  GENERATED FILES:")
        for f in final_result.files:
            report_lines.append(f"    📄 {f.file_path}")

        if final_report_data:
            report_lines.append(f"\n  FINAL DIMENSION SCORES:")
            for dim in final_report_data.dimensions:
                status = "✓" if dim.passed else "✗"
                report_lines.append(
                    f"    {status} {dim.name:<25} {dim.score:.1f}% "
                    f"(threshold: {dim.threshold:.0f}%)"
                )

            failing = final_report_data.failing_dimensions
            if failing:
                report_lines.append(f"\n  ⚠ DIMENSIONS STILL BELOW THRESHOLD ({len(failing)}):")
                for dim in sorted(failing, key=lambda d: d.score):
                    report_lines.append(f"    ❌ {dim.name}: {dim.score:.1f}% (need {dim.threshold:.0f}%)")

            remaining_gaps = final_report_data.all_missing_items
            if remaining_gaps:
                report_lines.append(f"\n  REMAINING GAPS ({len(remaining_gaps)}):")
                for item in remaining_gaps[:10]:
                    report_lines.append(f"    - {item}")

        report_lines.append(f"\n{'='*60}")
        return '\n'.join(report_lines)

    def save_generated_files(
        self, conversion_result: ConversionResult, program_id: str
    ) -> Path:
        """Save all generated files to the output directory."""
        program_dir = self.output_dir / program_id
        program_dir.mkdir(parents=True, exist_ok=True)

        for gen_file in conversion_result.files:
            file_path = program_dir / gen_file.file_path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(gen_file.content, encoding='utf-8')

        return program_dir

    def save_report_json(
        self,
        program_id: str,
        iterations: list[tuple[int, AccuracyReport]],
        final_result: ConversionResult,
        total_tokens: int,
    ) -> Path:
        """Save structured report as JSON."""
        report_data = {
            "program_id": program_id,
            "timestamp": datetime.now().isoformat(),
            "total_iterations": len(iterations),
            "total_tokens": total_tokens,
            "final_accuracy": iterations[-1][1].overall_score if iterations else 0,
            "iterations": [],
            "generated_files": [f.file_path for f in final_result.files],
        }

        for iteration, acc_report in iterations:
            iter_data = {
                "iteration": iteration,
                "overall_score": acc_report.overall_score,
                "dimensions": {},
            }
            for dim in acc_report.dimensions:
                iter_data["dimensions"][dim.name] = {
                    "score": dim.score,
                    "missing_count": len(dim.missing_items),
                    "incorrect_count": len(dim.incorrect_items),
                }
            report_data["iterations"].append(iter_data)

        report_path = self.output_dir / program_id / "migration_report.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report_data, indent=2), encoding='utf-8')
        return report_path

    def _progress_bar(self, score: float, width: int = 20) -> str:
        """Create a text-based progress bar."""
        filled = int(width * score / 100)
        bar = '█' * filled + '░' * (width - filled)
        return f"[{bar}]"
