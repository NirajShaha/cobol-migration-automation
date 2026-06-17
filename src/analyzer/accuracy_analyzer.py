"""Accuracy analyzer - evaluates migrated code against original COBOL/Telon source."""

import json
import re
from dataclasses import dataclass, field
from typing import Optional

from ..llm.base import BaseLLMProvider
from ..converter.code_converter import ConversionResult
from ..parser.cobol_parser import ParsedCobolProgram, CobolParser
from config.prompts.analysis_prompts import (
    ANALYSIS_SYSTEM_PROMPT,
    ACCURACY_ANALYSIS_PROMPT,
)
from config.settings import DIMENSION_THRESHOLDS


# Map internal keys to display names
DIMENSION_DISPLAY_NAMES = {
    "business_logic": "Business Logic",
    "error_handling": "Error Handling",
    "schema_mapping": "Schema & Table Mapping",
    "field_validation": "Field Validations",
    "ui_fields": "UI Fields",
    "error_messages": "Error Messages",
}


@dataclass
class DimensionScore:
    """Score for a single accuracy dimension."""
    name: str
    key: str
    score: float
    threshold: float
    matched_items: list[str] = field(default_factory=list)
    missing_items: list[str] = field(default_factory=list)
    incorrect_items: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """Whether this dimension meets its minimum threshold."""
        return self.score >= self.threshold


@dataclass
class AccuracyReport:
    """Complete accuracy analysis report."""
    overall_score: float = 0.0
    min_dimension_score: float = 0.0
    dimensions: list[DimensionScore] = field(default_factory=list)
    summary: str = ""
    iteration: int = 0
    raw_analysis: str = ""

    @property
    def all_dimensions_passed(self) -> bool:
        """True only if EVERY dimension meets its individual threshold."""
        return all(d.passed for d in self.dimensions) if self.dimensions else False

    @property
    def failing_dimensions(self) -> list[DimensionScore]:
        """Dimensions that haven't met their threshold yet."""
        return [d for d in self.dimensions if not d.passed]

    @property
    def all_missing_items(self) -> list[str]:
        """Get all missing items across dimensions."""
        items = []
        for dim in self.dimensions:
            for item in dim.missing_items:
                items.append(f"[{dim.name}] {item}")
        return items

    @property
    def all_incorrect_items(self) -> list[str]:
        """Get all incorrect items across dimensions."""
        items = []
        for dim in self.dimensions:
            for item in dim.incorrect_items:
                items.append(f"[{dim.name}] {item}")
        return items

    def get_gaps_report(self) -> str:
        """Format gaps for the refinement prompt, prioritizing failing dimensions."""
        lines = []
        # Show failing dimensions first (sorted lowest score first)
        sorted_dims = sorted(self.dimensions, key=lambda d: d.score)
        for dim in sorted_dims:
            if dim.missing_items or dim.incorrect_items:
                status = "❌ BELOW THRESHOLD" if not dim.passed else "✓ PASSED"
                lines.append(
                    f"\n## {dim.name} (Score: {dim.score}/100, "
                    f"Required: {dim.threshold}, {status})"
                )
                if dim.missing_items:
                    lines.append("Missing:")
                    for item in dim.missing_items:
                        lines.append(f"  - {item}")
                if dim.incorrect_items:
                    lines.append("Incorrect:")
                    for item in dim.incorrect_items:
                        lines.append(f"  - {item}")
        return '\n'.join(lines)


class AccuracyAnalyzer:
    """Analyzes accuracy of migrated code using LLM-based comparison."""

    def __init__(self, llm_provider: BaseLLMProvider, max_tokens: int = 4096):
        self.llm = llm_provider
        self.max_tokens = max_tokens
        self.parser = CobolParser()

    def analyze(
        self,
        source_code: str,
        conversion_result: ConversionResult,
        parsed_program: ParsedCobolProgram,
        iteration: int = 1,
    ) -> AccuracyReport:
        """Analyze accuracy of migrated code against original source."""
        # Format migrated code for analysis
        migrated_code = self._format_migrated_code(conversion_result)
        
        # Call LLM for detailed analysis
        prompt = ACCURACY_ANALYSIS_PROMPT.format(
            source_code=source_code,
            migrated_code=migrated_code,
        )
        
        response = self.llm.generate(
            system_prompt=ANALYSIS_SYSTEM_PROMPT,
            user_prompt=prompt,
            max_tokens=self.max_tokens,
            temperature=0.1,  # Low temperature for consistent analysis
        )
        
        # Parse the JSON analysis response
        report = self._parse_analysis_response(response.content, iteration)
        
        # Cross-validate with structural analysis
        structural_report = self._structural_analysis(
            parsed_program, conversion_result
        )
        
        # Merge LLM analysis with structural validation
        final_report = self._merge_reports(report, structural_report)
        final_report.raw_analysis = response.content
        
        return final_report

    def _format_migrated_code(self, conversion_result: ConversionResult) -> str:
        """Format conversion result for analysis prompt."""
        parts = []
        for f in conversion_result.files:
            parts.append(f"### FILE: {f.file_path}\n```{f.file_type}\n{f.content}\n```")
        return '\n\n'.join(parts)

    def _parse_analysis_response(self, response: str, iteration: int) -> AccuracyReport:
        """Parse the LLM's JSON analysis response."""
        json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', response, re.DOTALL)
        json_str = json_match.group(1) if json_match else response
        
        if not json_match:
            json_start = response.find('{')
            json_end = response.rfind('}')
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end + 1]
        
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            return AccuracyReport(
                overall_score=0.0,
                min_dimension_score=0.0,
                summary="Failed to parse analysis response",
                iteration=iteration,
                raw_analysis=response,
            )
        
        dimensions = []
        for key, display_name in DIMENSION_DISPLAY_NAMES.items():
            dim_data = data.get("dimensions", {}).get(key, {})
            threshold = DIMENSION_THRESHOLDS.get(key, 95.0)
            dimensions.append(DimensionScore(
                name=display_name,
                key=key,
                score=float(dim_data.get("score", 0)),
                threshold=threshold,
                matched_items=dim_data.get("matched_items", []),
                missing_items=dim_data.get("missing_items", []),
                incorrect_items=dim_data.get("incorrect_items", []),
            ))
        
        scores = [d.score for d in dimensions]
        overall = sum(scores) / len(scores) if scores else 0
        min_score = min(scores) if scores else 0
        
        return AccuracyReport(
            overall_score=round(overall, 2),
            min_dimension_score=round(min_score, 2),
            dimensions=dimensions,
            summary=data.get("summary", ""),
            iteration=iteration,
        )

    def _structural_analysis(
        self,
        parsed_program: ParsedCobolProgram,
        conversion_result: ConversionResult,
    ) -> AccuracyReport:
        """Perform structural analysis by checking for known elements in generated code."""
        all_code = '\n'.join(f.content for f in conversion_result.files)
        all_code_lower = all_code.lower()
        
        dimensions = []
        
        # Check paragraphs -> methods
        para_matched = []
        para_missing = []
        for para in parsed_program.paragraphs:
            method_name = self._cobol_to_java_name(para.name)
            if method_name.lower() in all_code_lower or para.name.lower().replace('-', '') in all_code_lower:
                para_matched.append(para.name)
            else:
                para_missing.append(f"Paragraph '{para.name}' has no equivalent method")
        
        para_score = (len(para_matched) / max(len(parsed_program.paragraphs), 1)) * 100
        dimensions.append(DimensionScore(
            name="Business Logic",
            key="business_logic",
            score=para_score,
            threshold=DIMENSION_THRESHOLDS["business_logic"],
            matched_items=para_matched,
            missing_items=para_missing,
        ))
        
        # Check error messages
        msg_matched = []
        msg_missing = []
        for msg in parsed_program.error_messages:
            if msg.message_text.lower() in all_code_lower:
                msg_matched.append(msg.message_text)
            else:
                msg_missing.append(f"Error message: '{msg.message_text}'")
        
        msg_score = (len(msg_matched) / max(len(parsed_program.error_messages), 1)) * 100
        dimensions.append(DimensionScore(
            name="Error Messages",
            key="error_messages",
            score=msg_score,
            threshold=DIMENSION_THRESHOLDS["error_messages"],
            matched_items=msg_matched,
            missing_items=msg_missing,
        ))
        
        # Check DB operations/tables
        db_matched = []
        db_missing = []
        tables_checked = set()
        for op in parsed_program.db_operations:
            table = op.table_or_file
            if table in tables_checked:
                continue
            tables_checked.add(table)
            table_variants = [
                table.lower(),
                table.lower().replace('-', '_'),
                table.lower().replace('-', ''),
                self._cobol_to_java_name(table).lower(),
            ]
            found = any(v in all_code_lower for v in table_variants)
            if found:
                db_matched.append(f"{op.operation_type} on {table}")
            else:
                db_missing.append(f"Table/File '{table}' not found in generated code")
        
        db_score = (len(db_matched) / max(len(tables_checked), 1)) * 100
        dimensions.append(DimensionScore(
            name="Schema & Table Mapping",
            key="schema_mapping",
            score=db_score,
            threshold=DIMENSION_THRESHOLDS["schema_mapping"],
            matched_items=db_matched,
            missing_items=db_missing,
        ))
        
        # Check validations
        val_matched = []
        val_missing = []
        for val in parsed_program.validations:
            field_variants = [
                val.field_name.lower(),
                val.field_name.lower().replace('-', '_'),
                self._cobol_to_java_name(val.field_name).lower(),
            ]
            found = any(v in all_code_lower for v in field_variants)
            if found:
                val_matched.append(f"{val.validation_type} check on {val.field_name}")
            else:
                val_missing.append(f"Validation '{val.validation_type}' on field '{val.field_name}'")
        
        val_score = (len(val_matched) / max(len(parsed_program.validations), 1)) * 100
        dimensions.append(DimensionScore(
            name="Field Validations",
            key="field_validation",
            score=val_score,
            threshold=DIMENSION_THRESHOLDS["field_validation"],
            matched_items=val_matched,
            missing_items=val_missing,
        ))
        
        # Check screen fields
        ui_matched = []
        ui_missing = []
        for sf in parsed_program.screen_fields:
            field_variants = [
                sf.name.lower(),
                sf.name.lower().replace('-', '_'),
                sf.name.lower().replace('-', ''),
                self._cobol_to_camel_case(sf.name).lower(),
            ]
            found = any(v in all_code_lower for v in field_variants)
            if found:
                ui_matched.append(sf.name)
            else:
                ui_missing.append(f"Screen field '{sf.name}' not found in UI code")
        
        ui_score = (len(ui_matched) / max(len(parsed_program.screen_fields), 1)) * 100
        dimensions.append(DimensionScore(
            name="UI Fields",
            key="ui_fields",
            score=ui_score,
            threshold=DIMENSION_THRESHOLDS["ui_fields"],
            matched_items=ui_matched,
            missing_items=ui_missing,
        ))
        
        # Error handling (structural check for try/catch patterns)
        error_patterns = ['try', 'catch', 'throw', 'exception', 'error']
        error_score = 50.0
        if any(p in all_code_lower for p in error_patterns):
            error_score = 70.0
        dimensions.append(DimensionScore(
            name="Error Handling",
            key="error_handling",
            score=error_score,
            threshold=DIMENSION_THRESHOLDS["error_handling"],
        ))
        
        scores = [d.score for d in dimensions]
        overall = sum(scores) / len(scores) if scores else 0
        min_score = min(scores) if scores else 0
        return AccuracyReport(
            overall_score=round(overall, 2),
            min_dimension_score=round(min_score, 2),
            dimensions=dimensions,
            summary="Structural analysis based on pattern matching",
        )

    def _merge_reports(
        self, llm_report: AccuracyReport, structural_report: AccuracyReport
    ) -> AccuracyReport:
        """Merge LLM and structural reports, taking the lower score for each dimension."""
        if not llm_report.dimensions:
            return structural_report
        if not structural_report.dimensions:
            return llm_report
        
        merged_dimensions = []
        struct_dims = {d.key: d for d in structural_report.dimensions}
        
        for llm_dim in llm_report.dimensions:
            struct_dim = struct_dims.get(llm_dim.key)
            if struct_dim:
                score = min(llm_dim.score, struct_dim.score)
                all_missing = list(set(llm_dim.missing_items + struct_dim.missing_items))
                merged_dimensions.append(DimensionScore(
                    name=llm_dim.name,
                    key=llm_dim.key,
                    score=score,
                    threshold=llm_dim.threshold,
                    matched_items=llm_dim.matched_items,
                    missing_items=all_missing,
                    incorrect_items=llm_dim.incorrect_items,
                ))
            else:
                merged_dimensions.append(llm_dim)
        
        scores = [d.score for d in merged_dimensions]
        overall = sum(scores) / len(scores) if scores else 0
        min_score = min(scores) if scores else 0
        return AccuracyReport(
            overall_score=round(overall, 2),
            min_dimension_score=round(min_score, 2),
            dimensions=merged_dimensions,
            summary=llm_report.summary,
            iteration=llm_report.iteration,
        )

    def _cobol_to_java_name(self, cobol_name: str) -> str:
        """Convert COBOL-STYLE-NAME to javaStyleName."""
        parts = cobol_name.lower().split('-')
        return parts[0] + ''.join(p.capitalize() for p in parts[1:])

    def _cobol_to_camel_case(self, cobol_name: str) -> str:
        """Convert COBOL-STYLE-NAME to CamelCase."""
        parts = cobol_name.lower().split('-')
        return ''.join(p.capitalize() for p in parts)
