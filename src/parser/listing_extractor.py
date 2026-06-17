"""Extracts raw COBOL source code from IBM Enterprise COBOL compiler listing files.

IBM COBOL compiler listings have a specific format:
- Page headers starting with '1PP 5655-S71...'
- Compiler options pages
- Library phase message pages
- Source code pages with line numbers, PL/SL columns, source, and cross-references

This module detects listing format and extracts just the COBOL source (columns 1-72).

Listing line layout (source pages):
  Positions 0-2:   Control char + spaces (e.g., '0  ', '   ', '-  ')
  Positions 3-8:   LineID (6-digit line number)
  Positions 9-17:  PL + SL columns + spacing
  Positions 18-89: COBOL source columns 1-72
  Position 89-90:  '|' separator (column 72/73 boundary)
  Positions 90+:   Cross-reference / Map info
"""

import re
from dataclasses import dataclass, field
from typing import Optional


# Pattern to identify page header lines
PAGE_HEADER_PATTERN = re.compile(r'^1PP\s+\d+-\S+\s+IBM\s+Enterprise\s+COBOL')

# Pattern for the column ruler line
RULER_PATTERN = re.compile(
    r'LineID\s+PL\s+SL\s+[-+\*A-Z0-9|]+'
)

# Pattern for source lines with a 6-digit line number
SOURCE_LINE_PATTERN = re.compile(r'^[0 \-]?\s{0,2}(\d{6})')

# Pattern for compiler message/options pages
OPTIONS_PATTERN = re.compile(r'^0?Options in effect:|^0?Invocation parameters:')
LIBRARY_MSG_PATTERN = re.compile(r'Library phase message text|Messages\s+Total\s+Informational')


@dataclass
class ExtractionResult:
    """Result of extracting source from a compiler listing."""
    source_code: str
    program_id: str = ""
    total_source_lines: int = 0
    pages_found: int = 0
    is_listing: bool = True
    warnings: list[str] = field(default_factory=list)


class ListingExtractor:
    """Extracts COBOL source code from IBM Enterprise COBOL compiler listing files."""

    # Position where COBOL columns 1-72 begin in the listing
    SOURCE_START_COL = 18
    # Position where COBOL column 72 ends (the '|' separator)
    SOURCE_END_COL = 90

    def is_compiler_listing(self, content: str) -> bool:
        """Detect whether the content is a compiler listing (vs raw COBOL source).

        Checks for IBM COBOL compiler listing page headers in the first few lines.
        """
        first_chunk = content[:2000]
        return bool(PAGE_HEADER_PATTERN.search(first_chunk))

    def extract(self, content: str) -> ExtractionResult:
        """Extract COBOL source code from a compiler listing.

        Args:
            content: Full text content of the compiler listing file

        Returns:
            ExtractionResult with the extracted source code and metadata
        """
        if not self.is_compiler_listing(content):
            # Not a listing - return as-is
            return ExtractionResult(
                source_code=content,
                is_listing=False,
                total_source_lines=len(content.splitlines()),
            )

        lines = content.splitlines()
        extracted_lines: list[str] = []
        pages_found = 0
        in_source_page = False
        skip_until_next_page = False

        i = 0
        while i < len(lines):
            line = lines[i]

            # Detect page headers
            if PAGE_HEADER_PATTERN.match(line):
                pages_found += 1
                # Check if this page is a source page (has ruler on next few lines)
                in_source_page = False
                skip_until_next_page = False
                # Look ahead for ruler line or options/messages
                for lookahead in range(1, min(4, len(lines) - i)):
                    next_line = lines[i + lookahead]
                    if RULER_PATTERN.search(next_line):
                        in_source_page = True
                        break
                    if OPTIONS_PATTERN.search(next_line) or LIBRARY_MSG_PATTERN.search(next_line):
                        skip_until_next_page = True
                        break
                i += 1
                continue

            # Skip non-source pages entirely
            if skip_until_next_page:
                i += 1
                continue

            # Skip the ruler line itself
            if RULER_PATTERN.search(line):
                i += 1
                continue

            # Process source lines
            if in_source_page:
                source_line = self._extract_source_line(line)
                if source_line is not None:
                    extracted_lines.append(source_line)

            i += 1

        # Build the source code
        source_code = '\n'.join(extracted_lines)

        # Extract program ID from the extracted source
        program_id = ""
        pid_match = re.search(r'PROGRAM-ID\.\s+(\S+)', source_code, re.IGNORECASE)
        if pid_match:
            program_id = pid_match.group(1).rstrip('.')

        return ExtractionResult(
            source_code=source_code,
            program_id=program_id,
            total_source_lines=len(extracted_lines),
            pages_found=pages_found,
            is_listing=True,
        )

    def _extract_source_line(self, line: str) -> Optional[str]:
        """Extract COBOL source columns from a single listing line.

        Returns the source code (columns 1-72) or None if this is not a source line.
        """
        # Must be long enough to contain at least the line number
        if len(line) < 9:
            return None

        # Check for 6-digit line number at positions 3-8 (accounting for control char)
        # Control character is at position 0 (space, '0', '1', '-')
        # Line number is typically at positions 3-8
        line_num_area = line[2:9].strip() if len(line) > 9 else ""

        # Try to find the line number - it could be at slightly different positions
        match = SOURCE_LINE_PATTERN.match(line)
        if not match:
            # Also check for lines without control chars (just spaces + number)
            stripped_start = line.lstrip()
            if stripped_start and stripped_start[0:6].isdigit():
                # Find where the number starts
                num_start = line.index(stripped_start[0])
                # Recalculate source start based on number position
                # Standard: number at pos 3-8, source at pos 18
                # Offset: source_start = num_start + 6 (number) + 9 (PL/SL/spaces)
                source_start = num_start + 15
                if source_start < len(line):
                    source_text = line[source_start:]
                    return self._clean_source(source_text)
            return None

        # Standard extraction: source code starts at position 18
        if len(line) > self.SOURCE_START_COL:
            source_text = line[self.SOURCE_START_COL:]
            return self._clean_source(source_text)
        else:
            # Short line - treat as blank source line
            return ""

    def _clean_source(self, source_text: str) -> str:
        """Clean extracted source text by removing cross-reference info.

        Strips everything after the '|' column separator (COBOL column 72 boundary).
        Also handles lines shorter than 72 characters.
        """
        # The '|' separator marks column 72/73 boundary
        # It's at a fixed position (72 chars into the source area)
        # But we look for it to handle slight variations
        pipe_pos = source_text.find('|')
        if pipe_pos > 0:
            # Take everything before the pipe, which is columns 1-72
            source_text = source_text[:pipe_pos]
        elif len(source_text) > 72:
            # No pipe found but line is too long - truncate at 72
            source_text = source_text[:72]

        # Right-strip trailing spaces but preserve leading spaces (significant in COBOL)
        return source_text.rstrip()
