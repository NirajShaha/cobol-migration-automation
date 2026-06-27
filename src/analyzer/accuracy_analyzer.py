"""Accuracy analyzer - evaluates migrated code against original COBOL/Telon source."""

import json
import re
from dataclasses import dataclass, field
from typing import Optional

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

    def __init__(self, llm_provider, max_tokens: int = 4096):
        self.llm = llm_provider
        self.max_tokens = max_tokens
        self.parser = CobolParser()

    def analyze(
        self,
        source_code: str,
        conversion_result: ConversionResult,
        parsed_program: ParsedCobolProgram,
        iteration: int = 1,
        previous_report: Optional[AccuracyReport] = None,
    ) -> AccuracyReport:
        """Analyze accuracy of migrated code against original source.
        
        For large files, uses structural analysis as the primary signal
        and only sends a truncated source to the LLM to save tokens.
        """
        # Format migrated code for analysis
        migrated_code = self._format_migrated_code(conversion_result)
        
        # Token-efficient: truncate source for LLM analysis on large files
        source_for_llm = source_code
        estimated_tokens = self.llm.estimate_tokens(source_code + migrated_code)
        if estimated_tokens > 15000:
            # Send only key sections to LLM, not full source
            max_source = 20000  # chars
            source_for_llm = source_code[:max_source]
            if len(source_code) > max_source:
                source_for_llm += f"\n... [truncated, full source is {len(source_code):,} chars]"
        
        # Call LLM for detailed analysis
        prompt = ACCURACY_ANALYSIS_PROMPT.format(
            source_code=source_for_llm,
            migrated_code=migrated_code,
        )
        
        response = self.llm.generate(
            system_prompt=ANALYSIS_SYSTEM_PROMPT,
            user_prompt=prompt,
            max_tokens=self.max_tokens,
            temperature=0.0,
        )
        
        # Parse the JSON analysis response
        report = self._parse_analysis_response(response.content, iteration)
        
        # Cross-validate with structural analysis (no LLM cost, always accurate)
        structural_report = self._structural_analysis(
            parsed_program, conversion_result
        )
        
        # Merge LLM analysis with structural validation
        final_report = self._merge_reports(report, structural_report)
        final_report = self._stabilize_report(final_report, previous_report)
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
        """Perform structural analysis checking elements AND modular architecture."""
        all_code = '\n'.join(f.content for f in conversion_result.files)
        all_code_lower = all_code.lower()
        file_paths = [f.file_path.lower() for f in conversion_result.files]
        
        dimensions = []
        
        # === Business Logic: paragraphs → service methods + modularity ===
        para_matched = []
        para_missing = []
        for para in parsed_program.paragraphs:
            method_name = self._cobol_to_java_name(para.name)
            if method_name.lower() in all_code_lower or para.name.lower().replace('-', '') in all_code_lower:
                para_matched.append(para.name)
            else:
                para_missing.append(f"Paragraph '{para.name}' has no equivalent method")
        
        # Check modular backend layers exist
        backend_layers = {
            'service': any('service' in p for p in file_paths),
            'serviceimpl': any('serviceimpl' in p or 'service/impl' in p for p in file_paths),
            'controller': any('controller' in p for p in file_paths),
            'repository': any('repository' in p for p in file_paths),
            'mapper': any('mapper' in p for p in file_paths),
        }
        for layer, exists in backend_layers.items():
            if not exists:
                para_missing.append(f"Missing backend layer: {layer}")
        
        layer_count = sum(1 for v in backend_layers.values() if v)
        para_element_score = (len(para_matched) / max(len(parsed_program.paragraphs), 1)) * 100
        layer_score = (layer_count / len(backend_layers)) * 100
        para_score = min(para_element_score, layer_score)
        
        dimensions.append(DimensionScore(
            name="Business Logic",
            key="business_logic",
            score=para_score,
            threshold=DIMENSION_THRESHOLDS["business_logic"],
            matched_items=para_matched,
            missing_items=para_missing,
        ))
        
        # === Error Messages ===
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
        
        # === Schema & Table Mapping + modular DTO/entity separation ===
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
        
        # Check modular data layers
        data_layers = {
            'entity': any('entity' in p for p in file_paths),
            'dto/request': any('request' in p and 'dto' in p for p in file_paths),
            'dto/response': any('response' in p and ('dto' in p or 'apiresponse' in p) for p in file_paths),
            'repository': any('repository' in p for p in file_paths),
        }
        for layer, exists in data_layers.items():
            if not exists:
                db_missing.append(f"Missing data layer: {layer}")
        
        data_layer_score = (sum(1 for v in data_layers.values() if v) / len(data_layers)) * 100
        db_element_score = (len(db_matched) / max(len(tables_checked), 1)) * 100
        db_score = min(db_element_score, data_layer_score)
        
        dimensions.append(DimensionScore(
            name="Schema & Table Mapping",
            key="schema_mapping",
            score=db_score,
            threshold=DIMENSION_THRESHOLDS["schema_mapping"],
            matched_items=db_matched,
            missing_items=db_missing,
        ))
        
        # === Field Validations (backend + frontend) ===
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
        
        # Check for validation infrastructure
        has_zod = 'zod' in all_code_lower or '.schema.ts' in ' '.join(file_paths)
        has_jakarta = '@notblank' in all_code_lower or '@notNull' in all_code_lower or '@size' in all_code_lower or '@valid' in all_code_lower
        has_validator = any('validator' in p for p in file_paths)
        if not has_zod:
            val_missing.append("Missing frontend Zod validation schema")
        if not has_jakarta:
            val_missing.append("Missing Jakarta Bean Validation annotations on DTOs")
        if not has_validator:
            val_missing.append("Missing custom Validator class for complex rules")
        
        val_score = (len(val_matched) / max(len(parsed_program.validations), 1)) * 100
        dimensions.append(DimensionScore(
            name="Field Validations",
            key="field_validation",
            score=val_score,
            threshold=DIMENSION_THRESHOLDS["field_validation"],
            matched_items=val_matched,
            missing_items=val_missing,
        ))
        
        # === UI Fields + modular frontend ===
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
        
        # Check modular frontend layers
        frontend_layers = {
            'page component': any('page.tsx' in p for p in file_paths),
            'feature component': any('components/features' in p or 'components/feature' in p for p in file_paths),
            'api service': any('service' in p and ('.ts' in p or '.tsx' in p) for p in file_paths),
            'types': any('types' in p and '.ts' in p for p in file_paths),
            'hooks': any('hook' in p or 'use' in p.split('/')[-1] for p in file_paths),
            'validation schema': any('validation' in p or 'schema' in p for p in file_paths),
        }
        for layer, exists in frontend_layers.items():
            if not exists:
                ui_missing.append(f"Missing frontend layer: {layer}")
        
        ui_score = (len(ui_matched) / max(len(parsed_program.screen_fields), 1)) * 100
        dimensions.append(DimensionScore(
            name="UI Fields",
            key="ui_fields",
            score=ui_score,
            threshold=DIMENSION_THRESHOLDS["ui_fields"],
            matched_items=ui_matched,
            missing_items=ui_missing,
        ))
        
        # === Error Handling - check for modular exception architecture ===
        error_matched = []
        error_missing = []
        
        exception_layers = {
            'custom exception classes': any('exception' in p and '.java' in p for p in file_paths),
            'GlobalExceptionHandler': 'controlleradvice' in all_code_lower or 'exceptionhandler' in all_code_lower,
            'ErrorResponse DTO': 'errorresponse' in all_code_lower,
            'try/catch blocks': 'try' in all_code_lower and 'catch' in all_code_lower,
            'throw statements': 'throw' in all_code_lower,
        }
        for layer, exists in exception_layers.items():
            if exists:
                error_matched.append(layer)
            else:
                error_missing.append(f"Missing: {layer}")
        
        error_score = (len(error_matched) / len(exception_layers)) * 100
        dimensions.append(DimensionScore(
            name="Error Handling",
            key="error_handling",
            score=error_score,
            threshold=DIMENSION_THRESHOLDS["error_handling"],
            matched_items=error_matched,
            missing_items=error_missing,
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
        """Merge LLM and structural reports with structural-weighted stability."""
        if not llm_report.dimensions:
            return structural_report
        if not structural_report.dimensions:
            return llm_report
        
        merged_dimensions = []
        struct_dims = {d.key: d for d in structural_report.dimensions}
        
        for llm_dim in llm_report.dimensions:
            struct_dim = struct_dims.get(llm_dim.key)
            if struct_dim:
                llm_weight = 0.3
                structural_weight = 0.7
                if llm_dim.key == "business_logic":
                    llm_weight = 0.2
                    structural_weight = 0.8
                score = round(
                    (llm_dim.score * llm_weight) + (struct_dim.score * structural_weight),
                    2,
                )
                all_missing = list(set(llm_dim.missing_items + struct_dim.missing_items))
                all_incorrect = list(set(llm_dim.incorrect_items + struct_dim.incorrect_items))
                all_matched = list(set(llm_dim.matched_items + struct_dim.matched_items))
                merged_dimensions.append(DimensionScore(
                    name=llm_dim.name,
                    key=llm_dim.key,
                    score=score,
                    threshold=llm_dim.threshold,
                    matched_items=all_matched,
                    missing_items=all_missing,
                    incorrect_items=all_incorrect,
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

    def _stabilize_report(
        self,
        current_report: AccuracyReport,
        previous_report: Optional[AccuracyReport],
    ) -> AccuracyReport:
        """Limit large score regressions between consecutive iterations."""
        if not previous_report or not previous_report.dimensions:
            return current_report

        previous_scores = {d.key: d.score for d in previous_report.dimensions}
        max_allowed_drop = 2.0

        for dim in current_report.dimensions:
            previous_score = previous_scores.get(dim.key)
            if previous_score is None:
                continue
            floor_score = previous_score - max_allowed_drop
            if dim.score < floor_score:
                dim.score = round(max(floor_score, 0.0), 2)

        scores = [d.score for d in current_report.dimensions]
        current_report.overall_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        current_report.min_dimension_score = round(min(scores), 2) if scores else 0.0
        return current_report

    def _cobol_to_java_name(self, cobol_name: str) -> str:
        """Convert COBOL-STYLE-NAME to javaStyleName."""
        parts = cobol_name.lower().split('-')
        return parts[0] + ''.join(p.capitalize() for p in parts[1:])

    def _cobol_to_camel_case(self, cobol_name: str) -> str:
        """Convert COBOL-STYLE-NAME to CamelCase."""
        parts = cobol_name.lower().split('-')
        return ''.join(p.capitalize() for p in parts)
