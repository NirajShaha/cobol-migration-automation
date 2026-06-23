"""Code converter - orchestrates LLM calls for COBOL to Spring Boot + Next.js conversion."""

import re
from dataclasses import dataclass, field
from typing import Optional, Any, Protocol, runtime_checkable

from ..parser.cobol_parser import ParsedCobolProgram
from config.prompts.conversion_prompts import (
    SYSTEM_PROMPT,
    INITIAL_CONVERSION_PROMPT,
    REFINEMENT_PROMPT,
    CHUNKED_SYSTEM_PROMPT,
    CHUNKED_ENTITY_PROMPT,
    CHUNKED_REPOSITORY_PROMPT,
    CHUNKED_DTO_PROMPT,
    CHUNKED_SERVICE_PROMPT,
    CHUNKED_CONTROLLER_PROMPT,
    CHUNKED_FRONTEND_PROMPT,
    LARGE_SOURCE_THRESHOLD,
)


@runtime_checkable
class LLMInterface(Protocol):
    """Protocol for LLM providers — supports both old and new provider interfaces."""
    def generate(self, system_prompt: str, user_prompt: str, max_tokens: int = ..., temperature: float = ...) -> Any: ...
    def estimate_tokens(self, text: str) -> int: ...


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

    def __init__(self, llm_provider, max_tokens: int = 16384):
        self.llm = llm_provider
        self.max_tokens = max_tokens

    def initial_conversion(
        self, source_code: str, parsed_program: ParsedCobolProgram
    ) -> ConversionResult:
        """Perform the initial conversion of COBOL/Telon to modern stack.
        
        Automatically switches to chunked mode for large programs.
        """
        estimated_tokens = self.llm.estimate_tokens(source_code)
        
        if estimated_tokens > LARGE_SOURCE_THRESHOLD:
            return self._chunked_conversion(source_code, parsed_program)
        
        return self._single_pass_conversion(source_code, parsed_program)

    def _single_pass_conversion(
        self, source_code: str, parsed_program: ParsedCobolProgram
    ) -> ConversionResult:
        """Standard single-pass conversion for smaller programs."""
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

    def _chunked_conversion(
        self, source_code: str, parsed_program: ParsedCobolProgram
    ) -> ConversionResult:
        """Multi-pass conversion for large programs — one layer per LLM call."""
        all_files: list[GeneratedFile] = []
        total_tokens = 0
        raw_responses: list[str] = []
        
        # Prepare summarized context from parsed program
        source_summary = self._get_source_summary(source_code, parsed_program)
        data_fields = self._format_data_fields(parsed_program)
        db_operations = self._format_db_operations(parsed_program)
        validations = self._format_validations(parsed_program)
        screen_fields = self._format_screen_fields(parsed_program)
        error_messages = self._format_error_messages(parsed_program)
        paragraphs_source = self._format_paragraphs(source_code, parsed_program)
        
        # --- Pass 1: Entities ---
        prompt = CHUNKED_ENTITY_PROMPT.format(
            source_summary=source_summary,
            data_fields=data_fields,
            db_operations=db_operations,
        )
        files, tokens, raw = self._call_chunked(prompt)
        all_files.extend(files)
        total_tokens += tokens
        raw_responses.append(raw)
        
        entities_code = self._format_generated_code(
            [f for f in all_files if 'entity' in f.file_path.lower()]
        )
        
        # --- Pass 2: Repositories ---
        prompt = CHUNKED_REPOSITORY_PROMPT.format(
            entities_code=entities_code,
            db_operations=db_operations,
        )
        files, tokens, raw = self._call_chunked(prompt)
        all_files.extend(files)
        total_tokens += tokens
        raw_responses.append(raw)
        
        repositories_code = self._format_generated_code(
            [f for f in all_files if 'repository' in f.file_path.lower()]
        )
        
        # --- Pass 3: DTOs ---
        prompt = CHUNKED_DTO_PROMPT.format(
            entities_code=entities_code,
            validations=validations,
            screen_fields=screen_fields,
        )
        files, tokens, raw = self._call_chunked(prompt)
        all_files.extend(files)
        total_tokens += tokens
        raw_responses.append(raw)
        
        dtos_code = self._format_generated_code(
            [f for f in all_files if 'dto' in f.file_path.lower()]
        )
        
        # --- Pass 4: Services (business logic) ---
        prompt = CHUNKED_SERVICE_PROMPT.format(
            paragraphs_source=paragraphs_source,
            entities_code=entities_code,
            repositories_code=repositories_code,
            error_messages=error_messages,
        )
        files, tokens, raw = self._call_chunked(prompt)
        all_files.extend(files)
        total_tokens += tokens
        raw_responses.append(raw)
        
        services_code = self._format_generated_code(
            [f for f in all_files if 'service' in f.file_path.lower()]
        )
        
        # --- Pass 5: Controllers, Exceptions, Config ---
        prompt = CHUNKED_CONTROLLER_PROMPT.format(
            services_code=services_code,
            dtos_code=dtos_code,
            error_messages=error_messages,
        )
        files, tokens, raw = self._call_chunked(prompt)
        all_files.extend(files)
        total_tokens += tokens
        raw_responses.append(raw)
        
        controllers_code = self._format_generated_code(
            [f for f in all_files if 'controller' in f.file_path.lower()]
        )
        
        # --- Pass 6: Frontend ---
        prompt = CHUNKED_FRONTEND_PROMPT.format(
            screen_fields=screen_fields,
            validations=validations,
            error_messages=error_messages,
            dtos_code=dtos_code,
            controllers_code=controllers_code,
        )
        files, tokens, raw = self._call_chunked(prompt)
        all_files.extend(files)
        total_tokens += tokens
        raw_responses.append(raw)
        
        return ConversionResult(
            files=all_files,
            raw_response='\n\n---\n\n'.join(raw_responses),
            iteration=1,
            tokens_used=total_tokens,
        )

    def _call_chunked(self, prompt: str) -> tuple[list['GeneratedFile'], int, str]:
        """Make a single chunked LLM call and return parsed files + tokens."""
        response = self.llm.generate(
            system_prompt=CHUNKED_SYSTEM_PROMPT,
            user_prompt=prompt,
            max_tokens=self.max_tokens,
            temperature=0.2,
        )
        files = self._parse_generated_files(response.content)
        tokens = response.input_tokens + response.output_tokens
        return files, tokens, response.content

    def _get_source_summary(
        self, source_code: str, parsed_program: ParsedCobolProgram
    ) -> str:
        """Extract a compact summary of the source for context.
        
        For large files, returns the DATA DIVISION + key sections (not the full source).
        """
        lines = source_code.split('\n')
        
        # Try to extract just the DATA DIVISION (field definitions)
        data_start = None
        procedure_start = None
        for i, line in enumerate(lines):
            upper = line.upper().strip()
            if 'DATA DIVISION' in upper:
                data_start = i
            if 'PROCEDURE DIVISION' in upper:
                procedure_start = i
                break
        
        if data_start is not None and procedure_start is not None:
            data_section = '\n'.join(lines[data_start:procedure_start])
            # Cap at ~8000 chars to stay within context limits
            if len(data_section) > 8000:
                data_section = data_section[:8000] + "\n... [truncated]"
            return data_section
        
        # Fallback: first 8000 chars of source
        if len(source_code) > 8000:
            return source_code[:8000] + "\n... [truncated]"
        return source_code

    def _format_data_fields(self, parsed_program: ParsedCobolProgram) -> str:
        """Format parsed data fields as concise text."""
        lines = []
        for f in parsed_program.working_storage_fields[:200]:  # Cap to avoid token overflow
            line = f"  {f.level:02d} {f.name}"
            if f.picture:
                line += f" PIC {f.picture}"
            if f.value:
                line += f" VALUE {f.value}"
            lines.append(line)
        if len(parsed_program.working_storage_fields) > 200:
            lines.append(f"  ... and {len(parsed_program.working_storage_fields) - 200} more fields")
        return '\n'.join(lines) if lines else "No fields parsed."

    def _format_db_operations(self, parsed_program: ParsedCobolProgram) -> str:
        """Format DB operations list."""
        lines = []
        for op in parsed_program.db_operations:
            line = f"- {op.operation_type} on {op.table_or_file}"
            if op.conditions:
                line += f" WHERE {op.conditions}"
            lines.append(line)
        return '\n'.join(lines) if lines else "No DB operations found."

    def _format_validations(self, parsed_program: ParsedCobolProgram) -> str:
        """Format validations list."""
        lines = []
        for v in parsed_program.validations:
            line = f"- {v.validation_type} check on {v.field_name}"
            if v.condition:
                line += f" ({v.condition})"
            lines.append(line)
        return '\n'.join(lines) if lines else "No explicit validations found."

    def _format_screen_fields(self, parsed_program: ParsedCobolProgram) -> str:
        """Format screen fields list."""
        lines = []
        for sf in parsed_program.screen_fields:
            line = f"- {sf.name} (type={sf.field_type}, len={sf.length})"
            if sf.label:
                line += f" label='{sf.label}'"
            lines.append(line)
        return '\n'.join(lines) if lines else "No screen fields found."

    def _format_error_messages(self, parsed_program: ParsedCobolProgram) -> str:
        """Format error messages list."""
        lines = []
        for msg in parsed_program.error_messages:
            lines.append(f"- [{msg.identifier}] \"{msg.message_text}\"")
        return '\n'.join(lines) if lines else "No error messages found."

    def _format_paragraphs(
        self, source_code: str, parsed_program: ParsedCobolProgram
    ) -> str:
        """Format paragraph bodies for service generation.
        
        For very large programs, include paragraph names + bodies (capped).
        """
        parts = []
        total_chars = 0
        max_chars = 30000  # Cap total paragraph text
        
        for para in parsed_program.paragraphs:
            entry = f"{para.name}.\n{para.body}\n"
            if total_chars + len(entry) > max_chars:
                parts.append(f"... and {len(parsed_program.paragraphs) - len(parts)} more paragraphs")
                break
            parts.append(entry)
            total_chars += len(entry)
        
        return '\n'.join(parts) if parts else "No paragraphs parsed."

    def refine_conversion(
        self,
        source_code: str,
        previous_result: ConversionResult,
        accuracy_score: float,
        accuracy_report: str,
        missing_items: str,
        iteration: int,
    ) -> ConversionResult:
        """Refine a previous conversion based on accuracy analysis.
        
        For large files, uses a focused refinement targeting only the gaps.
        """
        generated_code = self._format_generated_code(previous_result.files)
        
        # For large source, truncate source_code in refinement prompt
        # to avoid exceeding context window
        source_for_prompt = source_code
        estimated_tokens = self.llm.estimate_tokens(source_code)
        if estimated_tokens > LARGE_SOURCE_THRESHOLD:
            # Include just enough source for context
            max_source_chars = 20000
            source_for_prompt = source_code[:max_source_chars]
            if len(source_code) > max_source_chars:
                source_for_prompt += (
                    f"\n\n... [Source truncated — full program is "
                    f"{len(source_code):,} chars / ~{estimated_tokens:,} tokens]\n"
                    f"Focus on the gaps listed above rather than re-reading the full source."
                )
        
        prompt = REFINEMENT_PROMPT.format(
            accuracy_score=accuracy_score,
            accuracy_report=accuracy_report,
            missing_items=missing_items,
            source_code=source_for_prompt,
            generated_code=generated_code,
        )
        
        response = self.llm.generate(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=prompt,
            max_tokens=self.max_tokens,
            temperature=0.2,
        )
        
        files = self._parse_generated_files(response.content)
        
        # If parsing yielded new files, merge with previous (keep files not re-generated)
        if files:
            files = self._merge_file_sets(previous_result.files, files)
        else:
            files = previous_result.files
        
        return ConversionResult(
            files=files,
            raw_response=response.content,
            iteration=iteration,
            tokens_used=response.input_tokens + response.output_tokens,
        )

    def _merge_file_sets(
        self, previous: list[GeneratedFile], new: list[GeneratedFile]
    ) -> list[GeneratedFile]:
        """Merge new files into previous set — new files override by path."""
        file_map = {f.file_path: f for f in previous}
        for f in new:
            file_map[f.file_path] = f
        return list(file_map.values())

    def _parse_generated_files(self, response: str) -> list[GeneratedFile]:
        """Parse the LLM response into individual files."""
        files = []
        
        # Pattern: ### FILE: path/to/file.ext followed by code block
        # Allow optional blank lines between the header and code fence
        file_pattern = r'###\s*FILE:\s*(.+?)\s*\n\s*```(?:\w+)?\n(.*?)```'
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
        # This handles variations like "## FILE:", "# FILE:", etc.
        if not files:
            sections = re.split(
                r'(?:^|\n)(?:#{1,3})\s*(?:FILE|file|File)[:\s]+',
                response
            )
            for section in sections[1:]:
                lines = section.strip().split('\n')
                if lines:
                    path = lines[0].strip().rstrip(':')
                    content = '\n'.join(lines[1:])
                    content = re.sub(r'^```\w*\n?', '', content)
                    content = re.sub(r'\n?```\s*$', '', content)
                    if path and content.strip():
                        files.append(GeneratedFile(
                            file_path=path,
                            content=content.strip(),
                            file_type=self._get_file_type(path),
                        ))
        
        # Final fallback: handle truncated responses
        if not files:
            header_pattern = r'(?:^|\n)#+\s*(?:FILE|File|file)\s*[:\s]+\s*(\S+.*?)\s*\n'
            headers = list(re.finditer(header_pattern, response))
            for i, header_match in enumerate(headers):
                path = header_match.group(1).strip().rstrip(':')
                start = header_match.end()
                end = headers[i + 1].start() if i + 1 < len(headers) else len(response)
                content = response[start:end]
                content = re.sub(r'^```\w*\n?', '', content.strip())
                content = re.sub(r'\n?```\s*$', '', content)
                if path and content.strip():
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
