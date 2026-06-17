"""Main orchestrator - drives the iterative migration pipeline."""

import time
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from .llm import create_llm_provider, BaseLLMProvider
from .parser import CobolParser, ParsedCobolProgram
from .converter import CodeConverter, ConversionResult
from .analyzer import AccuracyAnalyzer, AccuracyReport
from .reporter import MigrationReporter
from config import settings


console = Console()


class MigrationOrchestrator:
    """Orchestrates the complete COBOL/Telon to Spring Boot + Next.js migration pipeline."""

    def __init__(
        self,
        llm_provider: Optional[BaseLLMProvider] = None,
        max_iterations: int = None,
        target_accuracy: float = None,
        output_dir: Optional[Path] = None,
    ):
        self.llm = llm_provider or self._create_default_provider()
        self.max_iterations = max_iterations or settings.MAX_ITERATIONS
        self.target_accuracy = target_accuracy or settings.TARGET_ACCURACY
        self.output_dir = output_dir or settings.OUTPUT_DIR

        self.parser = CobolParser()
        self.converter = CodeConverter(self.llm, max_tokens=settings.MAX_TOKENS)
        self.analyzer = AccuracyAnalyzer(self.llm, max_tokens=settings.MAX_TOKENS)
        self.reporter = MigrationReporter(self.output_dir)

        self.total_tokens = 0
        self.iteration_history: list[tuple[int, AccuracyReport]] = []

    def migrate(self, source_file: Path) -> ConversionResult:
        """Execute the full migration pipeline with iterative refinement.
        
        Args:
            source_file: Path to the COBOL/Telon source file
            
        Returns:
            Final ConversionResult with all generated files
        """
        start_time = time.time()
        
        # Step 1: Read and parse the source code
        console.print(Panel("[bold blue]COBOL/Telon Migration Automation[/bold blue]", 
                           subtitle="Iterative Conversion Pipeline"))
        
        source_code = source_file.read_text(encoding='utf-8', errors='replace')
        console.print(f"\n📂 Source file: [cyan]{source_file.name}[/cyan]")
        console.print(f"📏 Source size: {len(source_code):,} characters")
        
        # Step 2: Parse COBOL structure
        console.print("\n🔍 Parsing COBOL/Telon structure...")
        parsed_program = self.parser.parse(source_code)
        summary = self.parser.get_summary(parsed_program)
        
        console.print(f"   Program ID: [green]{summary['program_id']}[/green]")
        console.print(f"   Paragraphs: {summary['total_paragraphs']}")
        console.print(f"   Data Fields: {summary['total_fields']}")
        console.print(f"   Screen Fields: {summary['total_screen_fields']}")
        console.print(f"   Error Messages: {summary['total_error_messages']}")
        console.print(f"   DB Operations: {summary['total_db_operations']}")
        console.print(f"   Validations: {summary['total_validations']}")
        
        # Step 3: Initial conversion
        console.print(f"\n{'━'*60}")
        console.print("[bold]Starting iterative conversion...[/bold]")
        console.print(f"   Target: ALL dimensions must individually score >= {self.target_accuracy}%")
        console.print(f"   Max iterations: {self.max_iterations}")
        console.print(f"{'━'*60}\n")
        
        current_result = self._perform_initial_conversion(source_code, parsed_program)
        
        # Step 4: Iterative refinement loop
        for iteration in range(1, self.max_iterations + 1):
            console.print(f"\n📊 [bold]Iteration {iteration}[/bold] - Analyzing accuracy...")
            
            # Analyze current result
            accuracy_report = self.analyzer.analyze(
                source_code, current_result, parsed_program, iteration
            )
            self.iteration_history.append((iteration, accuracy_report))
            
            # Print iteration report
            iter_report = self.reporter.generate_iteration_report(
                iteration, accuracy_report, current_result
            )
            console.print(iter_report)
            
            # Check if ALL dimensions meet their individual thresholds
            if accuracy_report.all_dimensions_passed:
                console.print(
                    f"\n✅ [bold green]All dimensions passed! "
                    f"Every dimension >= {self.target_accuracy}% "
                    f"(lowest: {accuracy_report.min_dimension_score:.1f}%)[/bold green]"
                )
                break
            
            # Show which dimensions are still failing
            failing = accuracy_report.failing_dimensions
            console.print(
                f"\n   ⚠ {len(failing)} dimension(s) below threshold:"
            )
            for dim in sorted(failing, key=lambda d: d.score):
                console.print(
                    f"     ❌ {dim.name}: {dim.score:.1f}% "
                    f"(need {dim.threshold}%)"
                )
            
            # Check if this is the last iteration
            if iteration >= self.max_iterations:
                console.print(
                    f"\n⚠️  [bold yellow]Max iterations ({self.max_iterations}) reached. "
                    f"{len(failing)} dimension(s) still below threshold.[/bold yellow]"
                )
                break
            
            # Refine the conversion
            console.print(f"\n🔧 Refining conversion (gaps identified)...")
            current_result = self._perform_refinement(
                source_code,
                current_result,
                accuracy_report,
                iteration + 1,
            )
        
        # Step 5: Save output and generate final report
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

    def _perform_initial_conversion(
        self, source_code: str, parsed_program: ParsedCobolProgram
    ) -> ConversionResult:
        """Perform the initial LLM-based conversion."""
        console.print("🚀 Performing initial conversion...")
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Converting COBOL/Telon to Spring Boot + Next.js...", total=None)
            result = self.converter.initial_conversion(source_code, parsed_program)
            progress.update(task, completed=True)
        
        self.total_tokens += result.tokens_used
        console.print(f"   ✓ Generated {len(result.files)} files ({result.tokens_used:,} tokens)")
        
        return result

    def _perform_refinement(
        self,
        source_code: str,
        current_result: ConversionResult,
        accuracy_report: AccuracyReport,
        iteration: int,
    ) -> ConversionResult:
        """Perform a refinement iteration."""
        gaps_report = accuracy_report.get_gaps_report()
        missing_items = '\n'.join(
            f"- {item}" for item in
            accuracy_report.all_missing_items + accuracy_report.all_incorrect_items
        )
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task(
                f"Refining conversion (iteration {iteration})...", total=None
            )
            result = self.converter.refine_conversion(
                source_code=source_code,
                previous_result=current_result,
                accuracy_score=accuracy_report.overall_score,
                accuracy_report=gaps_report,
                missing_items=missing_items,
                iteration=iteration,
            )
            progress.update(task, completed=True)
        
        self.total_tokens += result.tokens_used
        console.print(f"   ✓ Refined {len(result.files)} files ({result.tokens_used:,} tokens)")
        
        return result

    def _create_default_provider(self) -> BaseLLMProvider:
        """Create the default LLM provider from settings."""
        provider_config = {
            "nvidia": {
                "api_key": settings.NVIDIA_NIM_API_KEY,
                "model": settings.NVIDIA_NIM_MODEL,
                "base_url": settings.NVIDIA_NIM_BASE_URL,
            },
            "openai": {
                "api_key": settings.OPENAI_API_KEY,
                "model": settings.OPENAI_MODEL,
            },
            "azure": {
                "api_key": settings.AZURE_OPENAI_API_KEY,
                "endpoint": settings.AZURE_OPENAI_ENDPOINT,
                "deployment": settings.AZURE_OPENAI_DEPLOYMENT,
                "api_version": settings.AZURE_OPENAI_API_VERSION,
            },
            "anthropic": {
                "api_key": settings.ANTHROPIC_API_KEY,
                "model": settings.ANTHROPIC_MODEL,
            },
        }
        
        config = provider_config.get(settings.LLM_PROVIDER, {})
        return create_llm_provider(settings.LLM_PROVIDER, **config)
