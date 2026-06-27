"""Pipeline node functions — pure functions that transform PipelineState.

Each node:
1. Reads what it needs from state
2. Does its work (may call LLM)
3. Returns a dict of state updates
"""

from __future__ import annotations

import concurrent.futures
from typing import Any

from ..parser import CobolParser, ListingExtractor, ParsedCobolProgram
from ..converter.code_converter import (
    CodeConverter, ConversionResult, GeneratedFile,
)
from ..analyzer.accuracy_analyzer import AccuracyAnalyzer, AccuracyReport
from ..llm_providers import LLMProvider
from ..core.exceptions import ConversionError, AnalysisError, PipelineError
from ..core.logging import get_logger
from config.settings import settings

logger = get_logger("pipeline.nodes")


def parse_source(state: dict, llm: LLMProvider) -> dict:
    """Parse COBOL/Telon source — extract from listing if needed, then parse structure."""
    source_code = state["source_code"]
    
    # Extract from compiler listing format
    extractor = ListingExtractor()
    extraction = extractor.extract(source_code)
    
    if extraction.is_listing:
        source_code = extraction.source_code
        logger.info(
            "listing_extracted",
            pages=extraction.pages_found,
            lines=extraction.total_source_lines,
            program_id=extraction.program_id,
        )
    
    # Parse COBOL structure
    parser = CobolParser()
    parsed_program = parser.parse(source_code)
    
    # Estimate tokens to determine chunked vs single-pass
    estimated_tokens = llm.estimate_tokens(source_code)
    is_large = estimated_tokens > settings.pipeline.large_source_threshold
    
    logger.info(
        "source_parsed",
        program_id=parsed_program.program_id,
        paragraphs=len(parsed_program.paragraphs),
        fields=len(parsed_program.working_storage_fields),
        screen_fields=len(parsed_program.screen_fields),
        estimated_tokens=estimated_tokens,
        is_large_file=is_large,
    )
    
    return {
        "source_code": source_code,
        "parsed_program": parsed_program,
        "is_large_file": is_large,
        "estimated_tokens": estimated_tokens,
    }


def convert_code(state: dict, llm: LLMProvider) -> dict:
    """Convert COBOL to Spring Boot + Next.js — uses parallel chunked mode for large files."""
    source_code = state["source_code"]
    parsed_program = state["parsed_program"]
    is_large = state.get("is_large_file", False)
    
    converter = CodeConverter(llm, max_tokens=settings.llm.max_tokens)
    
    try:
        if is_large:
            logger.info("conversion_mode", mode="chunked_parallel")
            result = _parallel_chunked_conversion(converter, source_code, parsed_program)
        else:
            logger.info("conversion_mode", mode="single_pass")
            result = converter._single_pass_conversion(source_code, parsed_program)
    except Exception as e:
        logger.error("conversion_failed", error=str(e))
        raise ConversionError(f"Initial conversion failed: {e}", layer="all", iteration=1)
    
    logger.info(
        "conversion_complete",
        files_generated=len(result.files),
        tokens_used=result.tokens_used,
    )
    
    return {
        "conversion_result": result,
        "iteration": 1,
        "total_tokens": state.get("total_tokens", 0) + result.tokens_used,
    }


def _parallel_chunked_conversion(
    converter: CodeConverter,
    source_code: str,
    parsed_program: ParsedCobolProgram,
) -> ConversionResult:
    """Execute chunked conversion with parallelism where dependencies allow.
    
    Dependency graph:
      Phase 1 (parallel): entities
      Phase 2 (parallel): repositories, DTOs (both depend only on entities)
      Phase 3 (sequential): services (depends on entities + repos)
      Phase 4 (parallel): controllers + frontend (depend on services + DTOs)
    """
    all_files: list[GeneratedFile] = []
    total_tokens = 0
    raw_responses: list[str] = []
    
    # Prepare context
    source_summary = converter._get_source_summary(source_code, parsed_program)
    data_fields = converter._format_data_fields(parsed_program)
    db_operations = converter._format_db_operations(parsed_program)
    validations = converter._format_validations(parsed_program)
    screen_fields = converter._format_screen_fields(parsed_program)
    error_messages = converter._format_error_messages(parsed_program)
    paragraphs_source = converter._format_paragraphs(source_code, parsed_program)

    from config.prompts.conversion_prompts import (
        CHUNKED_ENTITY_PROMPT,
        CHUNKED_REPOSITORY_PROMPT,
        CHUNKED_DTO_PROMPT,
        CHUNKED_SERVICE_PROMPT,
        CHUNKED_CONTROLLER_PROMPT,
        CHUNKED_FRONTEND_PROMPT,
    )

    max_workers = settings.pipeline.max_parallel_calls

    # --- Phase 1: Entities (independent) ---
    entity_prompt = CHUNKED_ENTITY_PROMPT.format(
        source_summary=source_summary,
        data_fields=data_fields,
        db_operations=db_operations,
    )
    entity_files, tokens, raw = converter._call_chunked(entity_prompt)
    all_files.extend(entity_files)
    total_tokens += tokens
    raw_responses.append(raw)
    
    entities_code = converter._format_generated_code(
        [f for f in all_files if "entity" in f.file_path.lower()]
    )

    # --- Phase 2: Repositories + DTOs (parallel, both depend on entities) ---
    repo_prompt = CHUNKED_REPOSITORY_PROMPT.format(
        entities_code=entities_code,
        db_operations=db_operations,
    )
    dto_prompt = CHUNKED_DTO_PROMPT.format(
        entities_code=entities_code,
        validations=validations,
        screen_fields=screen_fields,
    )

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_repo = executor.submit(converter._call_chunked, repo_prompt)
        future_dto = executor.submit(converter._call_chunked, dto_prompt)
        
        repo_files, repo_tokens, repo_raw = future_repo.result()
        dto_files, dto_tokens, dto_raw = future_dto.result()

    all_files.extend(repo_files)
    all_files.extend(dto_files)
    total_tokens += repo_tokens + dto_tokens
    raw_responses.extend([repo_raw, dto_raw])
    
    repositories_code = converter._format_generated_code(
        [f for f in all_files if "repository" in f.file_path.lower()]
    )
    dtos_code = converter._format_generated_code(
        [f for f in all_files if "dto" in f.file_path.lower()]
    )

    # --- Phase 3: Services (depends on entities + repos) ---
    service_prompt = CHUNKED_SERVICE_PROMPT.format(
        paragraphs_source=paragraphs_source,
        entities_code=entities_code,
        repositories_code=repositories_code,
        error_messages=error_messages,
    )
    service_files, service_tokens, service_raw = converter._call_chunked(service_prompt)
    all_files.extend(service_files)
    total_tokens += service_tokens
    raw_responses.append(service_raw)
    
    services_code = converter._format_generated_code(
        [f for f in all_files if "service" in f.file_path.lower()]
    )

    # --- Phase 4: Controllers + Frontend (parallel) ---
    controller_prompt = CHUNKED_CONTROLLER_PROMPT.format(
        services_code=services_code,
        dtos_code=dtos_code,
        error_messages=error_messages,
    )
    frontend_prompt = CHUNKED_FRONTEND_PROMPT.format(
        screen_fields=screen_fields,
        validations=validations,
        error_messages=error_messages,
        dtos_code=dtos_code,
        controllers_code=services_code,  # Use services as context for frontend
    )

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_ctrl = executor.submit(converter._call_chunked, controller_prompt)
        future_fe = executor.submit(converter._call_chunked, frontend_prompt)
        
        ctrl_files, ctrl_tokens, ctrl_raw = future_ctrl.result()
        fe_files, fe_tokens, fe_raw = future_fe.result()

    all_files.extend(ctrl_files)
    all_files.extend(fe_files)
    total_tokens += ctrl_tokens + fe_tokens
    raw_responses.extend([ctrl_raw, fe_raw])

    return ConversionResult(
        files=all_files,
        raw_response="\n\n---\n\n".join(raw_responses),
        iteration=1,
        tokens_used=total_tokens,
    )


def analyze_accuracy(state: dict, llm: LLMProvider) -> dict:
    """Analyze conversion accuracy using structural + LLM analysis."""
    source_code = state["source_code"]
    conversion_result = state["conversion_result"]
    parsed_program = state["parsed_program"]
    iteration = state.get("iteration", 1)
    
    # Create adapter for backward compat with AccuracyAnalyzer
    analyzer = AccuracyAnalyzer(
        _LLMProviderAdapter(llm),
        max_tokens=settings.llm.max_tokens,
    )
    
    try:
        previous_report = state.get("iteration_history", [])[-1][1] if state.get("iteration_history") else None
        report = analyzer.analyze(
            source_code=source_code,
            conversion_result=conversion_result,
            parsed_program=parsed_program,
            iteration=iteration,
            previous_report=previous_report,
        )
    except Exception as e:
        logger.error("analysis_failed", error=str(e), iteration=iteration)
        # On analysis failure, create a minimal report so pipeline can continue
        report = AccuracyReport(
            overall_score=0.0,
            min_dimension_score=0.0,
            summary=f"Analysis failed: {e}",
            iteration=iteration,
        )
    
    # Update iteration history
    history = list(state.get("iteration_history", []))
    history.append((iteration, report))
    
    logger.info(
        "analysis_complete",
        iteration=iteration,
        overall_score=report.overall_score,
        min_score=report.min_dimension_score,
        dimensions_passed=sum(1 for d in report.dimensions if d.passed),
        total_dimensions=len(report.dimensions),
    )
    
    return {
        "accuracy_report": report,
        "iteration_history": history,
        "total_tokens": state.get("total_tokens", 0) + (
            llm.estimate_tokens(report.raw_analysis) if report.raw_analysis else 0
        ),
    }


def refine_code(state: dict, llm: LLMProvider) -> dict:
    """Refine conversion based on accuracy gaps."""
    source_code = state["source_code"]
    conversion_result = state["conversion_result"]
    accuracy_report = state["accuracy_report"]
    iteration = state.get("iteration", 1) + 1
    
    converter = CodeConverter(llm, max_tokens=settings.llm.max_tokens)
    
    gaps_report = accuracy_report.get_gaps_report()
    missing_items = "\n".join(
        f"- {item}"
        for item in accuracy_report.all_missing_items + accuracy_report.all_incorrect_items
    )
    
    try:
        result = converter.refine_conversion(
            source_code=source_code,
            previous_result=conversion_result,
            accuracy_score=accuracy_report.overall_score,
            accuracy_report=gaps_report,
            missing_items=missing_items,
            iteration=iteration,
        )
    except Exception as e:
        logger.error("refinement_failed", error=str(e), iteration=iteration)
        # Keep previous result on failure
        result = conversion_result
        result.iteration = iteration
    
    logger.info(
        "refinement_complete",
        iteration=iteration,
        files=len(result.files),
        tokens_used=result.tokens_used,
    )
    
    return {
        "conversion_result": result,
        "iteration": iteration,
        "total_tokens": state.get("total_tokens", 0) + result.tokens_used,
    }


def decide_next(state: dict, max_iterations: int) -> str:
    """Decide whether to refine, complete, or fail.
    
    Returns:
        "complete" - all dimensions passed
        "refine" - needs more work, iterations remaining
        "failed" - max iterations exhausted
    """
    report = state.get("accuracy_report")
    iteration = state.get("iteration", 0)
    
    if report and report.all_dimensions_passed:
        return "complete"
    
    if iteration >= max_iterations:
        logger.warning(
            "max_iterations_reached",
            iteration=iteration,
            max=max_iterations,
            score=report.overall_score if report else 0,
        )
        return "failed"
    
    return "refine"


class _LLMProviderAdapter:
    """Adapter: makes new LLMProvider compatible with old AccuracyAnalyzer interface."""
    
    def __init__(self, provider: LLMProvider):
        self._provider = provider
    
    def generate(
        self, system_prompt: str, user_prompt: str, max_tokens: int = 4096, temperature: float = 0.2
    ):
        result = self._provider.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        # Return object with .content, .input_tokens, .output_tokens for compat
        return result
    
    def estimate_tokens(self, text: str) -> int:
        return self._provider.estimate_tokens(text)
