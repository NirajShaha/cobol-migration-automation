"""COBOL/Telon to Spring Boot + Next.js Migration Automation Tool.

Usage:
    python run.py <input_file> [--provider openai|azure|anthropic] [--max-iterations 10] [--target-accuracy 95]

Examples:
    python run.py input/MY_PROGRAM.cbl
    python run.py input/MY_PROGRAM.cbl --provider azure --max-iterations 15
    python run.py input/MY_PROGRAM.cbl --target-accuracy 90
"""

import sys
import argparse
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.orchestrator import MigrationOrchestrator
from src.llm_providers import create_provider
from src.core import setup_logging, MigrationError, LLMProviderError
from config.settings import settings


def main():
    parser = argparse.ArgumentParser(
        description="Automated COBOL/Telon to Spring Boot + Next.js migration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run.py input/PAYROLL.cbl
  python run.py input/CUSTOMER.cbl --provider azure --max-iterations 15
  python run.py input/ORDER.telon --target-accuracy 90 --output ./my_output
        """,
    )
    parser.add_argument(
        "input_file",
        type=Path,
        help="Path to the COBOL/Telon source file",
    )
    parser.add_argument(
        "--provider",
        choices=["nvidia", "openai", "azure", "anthropic"],
        default=None,
        help=f"LLM provider to use (default: from .env = {settings.llm.provider})",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=None,
        help=f"Maximum refinement iterations (default: {settings.pipeline.max_iterations})",
    )
    parser.add_argument(
        "--target-accuracy",
        type=float,
        default=None,
        help=f"Target accuracy percentage (default: {settings.pipeline.target_accuracy})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=f"Output directory (default: {settings.output_dir})",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="API key (overrides .env file)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Model name override (e.g., gpt-4o, claude-sonnet-4-20250514)",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=None,
        help=f"Max tokens per LLM call (default: {settings.llm.max_tokens})",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default=None,
        help="Logging level (default: INFO)",
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(args.log_level)

    # Validate input file
    if not args.input_file.exists():
        print(f"Error: Input file not found: {args.input_file}")
        sys.exit(1)

    # Override settings if provided
    if args.max_tokens:
        settings.llm.max_tokens = args.max_tokens

    # Create provider
    provider_type = args.provider or settings.llm.provider
    try:
        llm_provider = create_provider(
            provider_type=provider_type,
            api_key=args.api_key,
            model=args.model,
        )
    except LLMProviderError as e:
        print(f"Error: {e}")
        print("Set API key in .env file or pass via --api-key argument.")
        print("See .env.example for configuration details.")
        sys.exit(1)

    # Run migration
    orchestrator = MigrationOrchestrator(
        llm_provider=llm_provider,
        max_iterations=args.max_iterations,
        target_accuracy=args.target_accuracy,
        output_dir=args.output,
    )

    try:
        result = orchestrator.migrate(args.input_file)
        print(f"\n✅ Migration complete! {len(result.files)} files generated.")
    except KeyboardInterrupt:
        print("\n\n⚠️  Migration interrupted by user.")
        sys.exit(130)
    except MigrationError as e:
        print(f"\n❌ Migration failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        raise


if __name__ == "__main__":
    main()
