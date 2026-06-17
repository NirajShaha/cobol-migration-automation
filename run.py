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
from src.llm import create_llm_provider
from config import settings


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
        help=f"LLM provider to use (default: from .env = {settings.LLM_PROVIDER})",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=None,
        help=f"Maximum refinement iterations (default: {settings.MAX_ITERATIONS})",
    )
    parser.add_argument(
        "--target-accuracy",
        type=float,
        default=None,
        help=f"Target accuracy percentage (default: {settings.TARGET_ACCURACY})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=f"Output directory (default: {settings.OUTPUT_DIR})",
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
        help=f"Max tokens per LLM call (default: {settings.MAX_TOKENS})",
    )

    args = parser.parse_args()

    # Validate input file
    if not args.input_file.exists():
        print(f"Error: Input file not found: {args.input_file}")
        sys.exit(1)

    # Determine provider and config
    provider_type = args.provider or settings.LLM_PROVIDER
    
    # Build provider kwargs
    provider_kwargs = {}
    if provider_type == "nvidia":
        provider_kwargs["api_key"] = args.api_key or settings.NVIDIA_NIM_API_KEY
        provider_kwargs["model"] = args.model or settings.NVIDIA_NIM_MODEL
        provider_kwargs["base_url"] = settings.NVIDIA_NIM_BASE_URL
    elif provider_type == "openai":
        provider_kwargs["api_key"] = args.api_key or settings.OPENAI_API_KEY
        provider_kwargs["model"] = args.model or settings.OPENAI_MODEL
    elif provider_type == "azure":
        provider_kwargs["api_key"] = args.api_key or settings.AZURE_OPENAI_API_KEY
        provider_kwargs["endpoint"] = settings.AZURE_OPENAI_ENDPOINT
        provider_kwargs["deployment"] = settings.AZURE_OPENAI_DEPLOYMENT
        provider_kwargs["api_version"] = settings.AZURE_OPENAI_API_VERSION
    elif provider_type == "anthropic":
        provider_kwargs["api_key"] = args.api_key or settings.ANTHROPIC_API_KEY
        provider_kwargs["model"] = args.model or settings.ANTHROPIC_MODEL

    # Validate API key
    if not provider_kwargs.get("api_key"):
        print(f"Error: No API key configured for provider '{provider_type}'.")
        print(f"Set it in .env file or pass via --api-key argument.")
        print(f"See .env.example for configuration details.")
        sys.exit(1)

    # Override max tokens if specified
    if args.max_tokens:
        settings.MAX_TOKENS = args.max_tokens

    # Create provider
    try:
        llm_provider = create_llm_provider(provider_type, **provider_kwargs)
    except Exception as e:
        print(f"Error creating LLM provider: {e}")
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
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        raise


if __name__ == "__main__":
    main()
