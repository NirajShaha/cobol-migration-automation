"""Main orchestrator — drives the migration pipeline using LangGraph.

Provides the CLI-facing interface with rich console output while delegating
the actual pipeline logic to the LangGraph state machine.
"""

import time
import re
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from .llm_providers import LLMProvider, create_provider
from .pipeline import MigrationPipeline, PipelineState
from .parser import CobolParser, ParsedCobolProgram, ListingExtractor
from .converter import CodeConverter, ConversionResult
from .analyzer import AccuracyAnalyzer, AccuracyReport
from .reporter import MigrationReporter
from .core import get_logger, setup_logging, MigrationError
from config.settings import settings

console = Console()
logger = get_logger("orchestrator")


class MigrationOrchestrator:
    """Orchestrates the COBOL/Telon to Spring Boot + Next.js migration.
    
    Uses LangGraph for the iterative pipeline while providing rich CLI output.
    """

    def __init__(
        self,
        llm_provider: Optional[LLMProvider] = None,
        max_iterations: int = None,
        target_accuracy: float = None,
        output_dir: Optional[Path] = None,
    ):
        self.llm = llm_provider or create_provider()
        self.max_iterations = max_iterations or settings.pipeline.max_iterations
        self.target_accuracy = target_accuracy or settings.pipeline.target_accuracy
        self.output_dir = output_dir or settings.output_dir

        self.reporter = MigrationReporter(self.output_dir)
        self.total_tokens = 0
        self.iteration_history: list[tuple[int, AccuracyReport]] = []
        self.best_scores: dict[str, float] = {}
        self.business_logic_graph: dict[str, str] = {}

    def migrate(self, source_file: Path) -> ConversionResult:
        """Execute the full migration pipeline.
        
        Args:
            source_file: Path to the COBOL/Telon source file
            
        Returns:
            Final ConversionResult with all generated files
            
        Raises:
            MigrationError: On unrecoverable pipeline failure
        """
        start_time = time.time()
        setup_logging()
        
        # Header
        console.print(Panel(
            "[bold blue]COBOL/Telon Migration Automation[/bold blue]",
            subtitle="Iterative Conversion Pipeline",
        ))
        
        source_code = source_file.read_text(encoding="utf-8", errors="replace")
        console.print(f"\n📂 Source file: [cyan]{source_file.name}[/cyan]")
        console.print(f"📏 Source size: {len(source_code):,} characters")
        
        # Step 1: Extract from listing if needed
        source_code = self._extract_listing(source_code)
        
        # Step 2: Parse COBOL structure
        parsed_program = self._parse_source(source_code)
        
        # Step 3: Initial conversion
        estimated_tokens = self.llm.estimate_tokens(source_code)
        is_large = estimated_tokens > settings.pipeline.large_source_threshold
        
        console.print(f"\n{'━' * 60}")
        console.print("[bold]Starting iterative conversion...[/bold]")
        console.print(f"   Target: ALL dimensions must individually score >= {self.target_accuracy}%")
        console.print(f"   Max iterations: {self.max_iterations}")
        if is_large:
            console.print(f"   Mode: [yellow]Chunked parallel[/yellow] (~{estimated_tokens:,} tokens)")
        console.print(f"{'━' * 60}\n")
        
        current_result = self._perform_initial_conversion(source_code, parsed_program, is_large)
        self._persist_snapshot(current_result, parsed_program, stage="initial", iteration=1)
        
        # Step 4: Iterative refinement loop
        for iteration in range(1, self.max_iterations + 1):
            console.print(f"\n📊 [bold]Iteration {iteration}[/bold] - Analyzing accuracy...")
            
            previous_report = self.iteration_history[-1][1] if self.iteration_history else None
            accuracy_report = self._perform_analysis(
                source_code, current_result, parsed_program, iteration, previous_report
            )
            self._update_business_logic_graph(accuracy_report)
            self._apply_monotonic_scores(accuracy_report)
            self.iteration_history.append((iteration, accuracy_report))
            
            # Print report
            iter_report = self.reporter.generate_iteration_report(
                iteration, accuracy_report, current_result
            )
            console.print(iter_report)
            
            # Check completion
            if accuracy_report.all_dimensions_passed:
                console.print(
                    f"\n✅ [bold green]All dimensions passed! "
                    f"Every dimension >= {self.target_accuracy}% "
                    f"(lowest: {accuracy_report.min_dimension_score:.1f}%)[/bold green]"
                )
                break
            
            # Show failing dimensions
            failing = accuracy_report.failing_dimensions
            console.print(f"\n   ⚠ {len(failing)} dimension(s) below threshold:")
            for dim in sorted(failing, key=lambda d: d.score):
                console.print(
                    f"     ❌ {dim.name}: {dim.score:.1f}% (need {dim.threshold}%)"
                )
            
            if iteration >= self.max_iterations:
                console.print(
                    f"\n⚠️  [bold yellow]Max iterations ({self.max_iterations}) reached. "
                    f"{len(failing)} dimension(s) still below threshold.[/bold yellow]"
                )
                break
            
            # Refine
            console.print(f"\n🔧 Refining conversion (gaps identified)...")
            current_result = self._perform_refinement(
                source_code, current_result, accuracy_report, iteration + 1
            )
            self._persist_snapshot(
                current_result,
                parsed_program,
                stage="refined",
                iteration=iteration + 1,
            )
        
        # Step 5: Save output
        elapsed = time.time() - start_time
        program_id = parsed_program.program_id or source_file.stem
        
        output_path = self.reporter.save_generated_files(current_result, program_id)
        self.reporter.save_report_json(
            program_id, self.iteration_history, current_result, self.total_tokens
        )
        
        final_report = self.reporter.generate_final_report(
            program_id, self.iteration_history, current_result,
            self.total_tokens, elapsed
        )
        console.print(final_report)
        console.print(f"\n📁 Output saved to: [cyan]{output_path}[/cyan]")
        
        return current_result

    def _extract_listing(self, source_code: str) -> str:
        """Extract clean source from compiler listing format."""
        extractor = ListingExtractor()
        extraction = extractor.extract(source_code)
        
        if extraction.is_listing:
            console.print(f"\n📋 [yellow]Detected IBM COBOL compiler listing format[/yellow]")
            console.print(f"   Pages found: {extraction.pages_found}")
            console.print(f"   Source lines extracted: {extraction.total_source_lines:,}")
            if extraction.program_id:
                console.print(f"   Program ID: [green]{extraction.program_id}[/green]")
            if extraction.warnings:
                for warn in extraction.warnings:
                    console.print(f"   ⚠ {warn}")
            source_code = extraction.source_code
            console.print(f"   Clean source size: {len(source_code):,} characters")
        
        return source_code

    def _parse_source(self, source_code: str) -> ParsedCobolProgram:
        """Parse COBOL/Telon structure."""
        console.print("\n🔍 Parsing COBOL/Telon structure...")
        parser = CobolParser()
        parsed_program = parser.parse(source_code)
        summary = parser.get_summary(parsed_program)
        
        console.print(f"   Program ID: [green]{summary['program_id']}[/green]")
        console.print(f"   Paragraphs: {summary['total_paragraphs']}")
        console.print(f"   Data Fields: {summary['total_fields']}")
        console.print(f"   Screen Fields: {summary['total_screen_fields']}")
        console.print(f"   Error Messages: {summary['total_error_messages']}")
        console.print(f"   DB Operations: {summary['total_db_operations']}")
        console.print(f"   Validations: {summary['total_validations']}")
        
        return parsed_program

    def _perform_initial_conversion(
        self, source_code: str, parsed_program: ParsedCobolProgram, is_large: bool
    ) -> ConversionResult:
        """Perform initial conversion with progress indicator."""
        if is_large:
            console.print(
                "🚀 Performing initial conversion "
                "([yellow]chunked parallel mode[/yellow])..."
            )
            console.print(
                "   Passes: entities → repos+DTOs (parallel) → services → controllers+frontend (parallel)"
            )
        else:
            console.print("🚀 Performing initial conversion...")
        
        converter = CodeConverter(self.llm, max_tokens=settings.llm.max_tokens)
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Converting COBOL/Telon to Spring Boot + Next.js...", total=None)
            
            if is_large:
                from .pipeline.nodes import _parallel_chunked_conversion
                result = _parallel_chunked_conversion(converter, source_code, parsed_program)
            else:
                result = converter._single_pass_conversion(source_code, parsed_program)
            
            progress.update(task, completed=True)
        
        self.total_tokens += result.tokens_used
        console.print(f"   ✓ Generated {len(result.files)} files ({result.tokens_used:,} tokens)")
        
        return result

    def _perform_analysis(
        self,
        source_code: str,
        conversion_result: ConversionResult,
        parsed_program: ParsedCobolProgram,
        iteration: int,
        previous_report: Optional[AccuracyReport] = None,
    ) -> AccuracyReport:
        """Perform accuracy analysis with error handling."""
        analyzer = AccuracyAnalyzer(self.llm, max_tokens=settings.llm.max_tokens)
        
        try:
            return analyzer.analyze(
                source_code=source_code,
                conversion_result=conversion_result,
                parsed_program=parsed_program,
                iteration=iteration,
                previous_report=previous_report,
            )
        except Exception as e:
            logger.error("analysis_error", error=str(e), iteration=iteration)
            # Return empty report on failure — pipeline continues
            return AccuracyReport(
                overall_score=0.0,
                min_dimension_score=0.0,
                summary=f"Analysis failed: {e}",
                iteration=iteration,
            )

    def _perform_refinement(
        self,
        source_code: str,
        current_result: ConversionResult,
        accuracy_report: AccuracyReport,
        iteration: int,
    ) -> ConversionResult:
        """Perform refinement with progress indicator."""
        converter = CodeConverter(self.llm, max_tokens=settings.llm.max_tokens)
        memory_context = self._build_memory_context()
        
        gaps_report = accuracy_report.get_gaps_report()
        missing_items = "\n".join(
            f"- {item}"
            for item in accuracy_report.all_missing_items + accuracy_report.all_incorrect_items
        )
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task(
                f"Refining conversion (iteration {iteration})...", total=None
            )
            result = converter.refine_conversion(
                source_code=source_code,
                previous_result=current_result,
                accuracy_score=accuracy_report.overall_score,
                accuracy_report=gaps_report,
                missing_items=missing_items,
                iteration=iteration,
                memory_context=memory_context,
            )
            progress.update(task, completed=True)
        
        self.total_tokens += result.tokens_used
        console.print(f"   ✓ Refined {len(result.files)} files ({result.tokens_used:,} tokens)")
        
        return result

    def _persist_snapshot(
        self,
        conversion_result: ConversionResult,
        parsed_program: ParsedCobolProgram,
        stage: str,
        iteration: int,
    ) -> None:
        """Persist intermediate outputs so container runs always write host-visible artifacts."""
        program_id = parsed_program.program_id or "UNKNOWN_PROGRAM"
        snapshot_id = f"{program_id}_{stage}_iter_{iteration}"
        self.reporter.save_generated_files(conversion_result, snapshot_id)

    def _apply_monotonic_scores(self, accuracy_report: AccuracyReport) -> None:
        """Ensure dimension scores never decrease across iterations."""
        for dim in accuracy_report.dimensions:
            previous_best = self.best_scores.get(dim.key)
            if previous_best is not None and dim.score < previous_best:
                dim.score = previous_best
            self.best_scores[dim.key] = dim.score

        scores = [d.score for d in accuracy_report.dimensions]
        accuracy_report.overall_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        accuracy_report.min_dimension_score = round(min(scores), 2) if scores else 0.0

    def _update_business_logic_graph(self, accuracy_report: AccuracyReport) -> None:
        """Maintain persistent paragraph status memory for business-logic refinement."""
        business_dim = next((d for d in accuracy_report.dimensions if d.key == "business_logic"), None)
        if not business_dim:
            return

        for item in business_dim.matched_items:
            name = item.strip()
            if name:
                self.business_logic_graph[name] = "matched"

        for item in business_dim.missing_items:
            paragraph_match = re.search(r"Paragraph '([^']+)'", item)
            if paragraph_match:
                self.business_logic_graph[paragraph_match.group(1)] = "missing"

    def _build_memory_context(self) -> str:
        """Create persistent memory context for refinement prompts."""
        if not self.business_logic_graph:
            return "No persistent business-logic graph yet."

        missing = sorted([k for k, v in self.business_logic_graph.items() if v == "missing"])
        matched = sorted([k for k, v in self.business_logic_graph.items() if v == "matched"])

        lines = [
            "Persistent Memory Graph:",
            f"- Matched paragraphs: {len(matched)}",
            f"- Missing paragraphs: {len(missing)}",
        ]

        if missing:
            lines.append("- Highest-priority unresolved paragraphs:")
            for name in missing[:50]:
                lines.append(f"  - {name}")

        return "\n".join(lines)
