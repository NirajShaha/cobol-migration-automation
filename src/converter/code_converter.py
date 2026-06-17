"""Code converter - orchestrates LLM calls for COBOL to Spring Boot + Next.js conversion."""

import re
from dataclasses import dataclass, field
from typing import Optional

from ..llm.base import BaseLLMProvider, LLMResponse
from ..parser.cobol_parser import ParsedCobolProgram
from config.prompts.conversion_prompts import (
    SYSTEM_PROMPT,
    INITIAL_CONVERSION_PROMPT,
    REFINEMENT_PROMPT,
)


@dataclass
class GeneratedFile:
    """Represents a single generated file."""
    file_path: str
    content: str
    file_type: str  # "java", "tsx", "ts", "sql"


@dataclass
class ConversionResult:
    """Result of a conversion attempt."""
    files: list[GeneratedFile] = field(default_factory=list)
    raw_response: str = ""
    iteration: int = 0
    tokens_used: int = 0


class CodeConverter:
    """Converts COBOL/Telon source to Spring Boot + Next.js using LLM."""

    def __init__(self, llm_provider: BaseLLMProvider, max_tokens: int = 4096):
        self.llm = llm_provider
        self.max_tokens = max_tokens

    def initial_conversion(
        self, source_code: str, parsed_program: ParsedCobolProgram
    ) -> ConversionResult:
        """Perform the initial conversion of COBOL/Telon to modern stack."""
        prompt = INITIAL_CONVERSION_PROMPT.format(source_code=source_code)
        
        response = self.llm.generate(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=prompt,
            max_tokens=self.max_tokens,
            temperature=0.2,
        )
        
        files = self._parse_generated_files(response.content)
        
        return ConversionResult(
            files=files,
            raw_response=response.content,
            iteration=1,
            tokens_used=response.input_tokens + response.output_tokens,
        )

    def refine_conversion(
        self,
        source_code: str,
        previous_result: ConversionResult,
        accuracy_score: float,
        accuracy_report: str,
        missing_items: str,
        iteration: int,
    ) -> ConversionResult:
        """Refine a previous conversion based on accuracy analysis."""
        generated_code = self._format_generated_code(previous_result.files)
        
        prompt = REFINEMENT_PROMPT.format(
            accuracy_score=accuracy_score,
            accuracy_report=accuracy_report,
            missing_items=missing_items,
            source_code=source_code,
            generated_code=generated_code,
        )
        
        response = self.llm.generate(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=prompt,
            max_tokens=self.max_tokens,
            temperature=0.2,
        )
        
        files = self._parse_generated_files(response.content)
        
        # If parsing failed, keep previous files as fallback
        if not files:
            files = previous_result.files
        
        return ConversionResult(
            files=files,
            raw_response=response.content,
            iteration=iteration,
            tokens_used=response.input_tokens + response.output_tokens,
        )

    def _parse_generated_files(self, response: str) -> list[GeneratedFile]:
        """Parse the LLM response into individual files."""
        files = []
        
        # Pattern: ### FILE: path/to/file.ext followed by code block
        file_pattern = r'###\s*FILE:\s*(.+?)\s*\n```(?:\w+)?\n(.*?)```'
        matches = re.findall(file_pattern, response, re.DOTALL)
        
        if not matches:
            # Try alternative format: ```java // filepath
            alt_pattern = r'```(\w+)\s*\n//\s*(?:File|Path):\s*(.+?)\n(.*?)```'
            alt_matches = re.findall(alt_pattern, response, re.DOTALL)
            for lang, path, content in alt_matches:
                file_type = self._get_file_type(path, lang)
                files.append(GeneratedFile(
                    file_path=path.strip(),
                    content=content.strip(),
                    file_type=file_type,
                ))
        else:
            for path, content in matches:
                file_type = self._get_file_type(path.strip())
                files.append(GeneratedFile(
                    file_path=path.strip(),
                    content=content.strip(),
                    file_type=file_type,
                ))
        
        # If still no files parsed, try to split by file markers
        if not files:
            sections = re.split(r'(?:^|\n)(?:#{1,3})\s*(?:FILE|file|File):\s*', response)
            for section in sections[1:]:  # Skip first empty section
                lines = section.strip().split('\n')
                if lines:
                    path = lines[0].strip()
                    content = '\n'.join(lines[1:])
                    # Remove code fence markers
                    content = re.sub(r'^```\w*\n?', '', content)
                    content = re.sub(r'\n?```\s*$', '', content)
                    if path and content:
                        files.append(GeneratedFile(
                            file_path=path,
                            content=content.strip(),
                            file_type=self._get_file_type(path),
                        ))
        
        return files

    def _get_file_type(self, file_path: str, lang_hint: str = "") -> str:
        """Determine file type from path or language hint."""
        if file_path.endswith('.java'):
            return 'java'
        elif file_path.endswith('.tsx'):
            return 'tsx'
        elif file_path.endswith('.ts'):
            return 'ts'
        elif file_path.endswith('.sql'):
            return 'sql'
        elif file_path.endswith('.yaml') or file_path.endswith('.yml'):
            return 'yaml'
        elif lang_hint:
            return lang_hint
        return 'unknown'

    def _format_generated_code(self, files: list[GeneratedFile]) -> str:
        """Format generated files back into a string for context."""
        parts = []
        for f in files:
            parts.append(f"### FILE: {f.file_path}\n```{f.file_type}\n{f.content}\n```")
        return '\n\n'.join(parts)
