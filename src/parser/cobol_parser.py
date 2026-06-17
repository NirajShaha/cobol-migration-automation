"""COBOL/Telon source code parser - extracts structural elements for analysis."""

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CobolField:
    """Represents a COBOL data field from WORKING-STORAGE or COPYBOOK."""
    level: int
    name: str
    picture: str = ""
    usage: str = ""
    value: str = ""
    occurs: int = 0
    redefines: str = ""


@dataclass
class CobolParagraph:
    """Represents a COBOL paragraph/section."""
    name: str
    body: str
    performs: list[str] = field(default_factory=list)
    conditions: list[str] = field(default_factory=list)


@dataclass
class ScreenField:
    """Represents a Telon screen field."""
    name: str
    field_type: str  # input, output, both
    row: int = 0
    col: int = 0
    length: int = 0
    label: str = ""
    attributes: list[str] = field(default_factory=list)


@dataclass
class ErrorMessage:
    """Represents an error message found in the source."""
    identifier: str
    message_text: str
    context: str = ""


@dataclass
class DatabaseOperation:
    """Represents a database/file operation."""
    operation_type: str  # READ, WRITE, REWRITE, DELETE, SELECT
    table_or_file: str
    conditions: str = ""
    fields: list[str] = field(default_factory=list)


@dataclass
class Validation:
    """Represents a field validation."""
    field_name: str
    validation_type: str  # NUMERIC, ALPHABETIC, NOT SPACES, LENGTH, RANGE
    condition: str = ""
    error_message: str = ""


@dataclass
class ParsedCobolProgram:
    """Complete parsed representation of a COBOL/Telon program."""
    program_id: str = ""
    working_storage_fields: list[CobolField] = field(default_factory=list)
    paragraphs: list[CobolParagraph] = field(default_factory=list)
    screen_fields: list[ScreenField] = field(default_factory=list)
    error_messages: list[ErrorMessage] = field(default_factory=list)
    db_operations: list[DatabaseOperation] = field(default_factory=list)
    validations: list[Validation] = field(default_factory=list)
    copybooks: list[str] = field(default_factory=list)
    file_definitions: list[str] = field(default_factory=list)


class CobolParser:
    """Parses COBOL/Telon source code to extract structural elements."""

    def parse(self, source_code: str) -> ParsedCobolProgram:
        """Parse COBOL/Telon source code and extract all elements."""
        program = ParsedCobolProgram()
        program.program_id = self._extract_program_id(source_code)
        program.working_storage_fields = self._extract_working_storage(source_code)
        program.paragraphs = self._extract_paragraphs(source_code)
        program.screen_fields = self._extract_screen_fields(source_code)
        program.error_messages = self._extract_error_messages(source_code)
        program.db_operations = self._extract_db_operations(source_code)
        program.validations = self._extract_validations(source_code)
        program.copybooks = self._extract_copybooks(source_code)
        program.file_definitions = self._extract_file_definitions(source_code)
        return program

    def _extract_program_id(self, source: str) -> str:
        match = re.search(r'PROGRAM-ID\.\s+(\S+)', source, re.IGNORECASE)
        return match.group(1).rstrip('.') if match else "UNKNOWN"

    def _extract_working_storage(self, source: str) -> list[CobolField]:
        fields = []
        # Match data definitions: level-number field-name PIC clause
        pattern = r'(\d{2})\s+([\w-]+)\s+(?:PIC(?:TURE)?\s+([^\s.]+))?'
        for match in re.finditer(pattern, source, re.IGNORECASE):
            level = int(match.group(1))
            name = match.group(2)
            picture = match.group(3) or ""
            
            # Skip level 88 (condition names) and FD entries
            if level == 88:
                continue
            
            field_obj = CobolField(level=level, name=name, picture=picture)
            
            # Check for VALUE clause
            value_match = re.search(
                rf'{re.escape(name)}.*?VALUE\s+([^\s.]+(?:\s+[^\s.]+)*)\.',
                source, re.IGNORECASE
            )
            if value_match:
                field_obj.value = value_match.group(1).strip("'\"")
            
            # Check for OCCURS clause
            occurs_match = re.search(
                rf'{re.escape(name)}.*?OCCURS\s+(\d+)',
                source, re.IGNORECASE
            )
            if occurs_match:
                field_obj.occurs = int(occurs_match.group(1))
            
            fields.append(field_obj)
        return fields

    def _extract_paragraphs(self, source: str) -> list[CobolParagraph]:
        paragraphs = []
        # Match paragraph headers (name followed by period at start of line)
        lines = source.split('\n')
        current_para = None
        current_body = []

        for line in lines:
            # Check if line starts a new paragraph (column 8, ends with period)
            stripped = line.strip()
            para_match = re.match(r'^([\w-]+)\.\s*$', stripped)
            
            # Keywords that are NOT paragraph names
            cobol_keywords = {
                'END-IF', 'END-EVALUATE', 'END-PERFORM', 'END-READ',
                'END-WRITE', 'END-REWRITE', 'END-DELETE', 'END-CALL',
                'END-STRING', 'END-UNSTRING', 'END-SEARCH', 'END-COMPUTE',
                'END-START', 'END-ACCEPT', 'END-DISPLAY', 'END-MULTIPLY',
                'END-DIVIDE', 'END-ADD', 'END-SUBTRACT', 'END-RETURN',
                'FILE-CONTROL', 'FILE-SECTION', 'WORKING-STORAGE',
                'PROCEDURE', 'DATA', 'ENVIRONMENT', 'IDENTIFICATION',
                'INPUT-OUTPUT', 'CONFIGURATION',
            }
            
            if (para_match 
                and not stripped.startswith(('0', '1', '2', '3', '4', '5', '6', '7', '8', '9'))
                and para_match.group(1).upper() not in cobol_keywords):
                # Save previous paragraph
                if current_para:
                    body = '\n'.join(current_body)
                    performs = re.findall(r'PERFORM\s+([\w-]+)', body, re.IGNORECASE)
                    conditions = re.findall(
                        r'(?:IF|EVALUATE|WHEN)\s+(.+?)(?:\s+THEN|\s*$)',
                        body, re.IGNORECASE
                    )
                    paragraphs.append(CobolParagraph(
                        name=current_para,
                        body=body,
                        performs=performs,
                        conditions=conditions,
                    ))
                current_para = para_match.group(1)
                current_body = []
            elif current_para:
                current_body.append(line)

        # Save last paragraph
        if current_para:
            body = '\n'.join(current_body)
            performs = re.findall(r'PERFORM\s+([\w-]+)', body, re.IGNORECASE)
            conditions = re.findall(
                r'(?:IF|EVALUATE|WHEN)\s+(.+?)(?:\s+THEN|\s*$)',
                body, re.IGNORECASE
            )
            paragraphs.append(CobolParagraph(
                name=current_para,
                body=body,
                performs=performs,
                conditions=conditions,
            ))

        return paragraphs

    def _extract_screen_fields(self, source: str) -> list[ScreenField]:
        fields = []
        # Telon screen field patterns (multiple formats)
        patterns = [
            # Format: FIELD name TYPE attributes
            r'(?:FIELD|FLD)\s+([\w-]+)\s+(?:TYPE\s+)?(\w+)(?:\s+LEN(?:GTH)?\s+(\d+))?',
            # Format: DEF FIELD name ROW col LEN
            r'DEF\s+(?:FIELD|FLD)\s+([\w-]+)\s+ROW\s+(\d+)\s+COL\s+(\d+)\s+LEN\s+(\d+)',
            # Format: screen map definitions
            r'(\d+)\s+(\d+)\s+([\w-]+)\s+(INPUT|OUTPUT|BOTH|I/O)',
        ]
        
        for pattern in patterns:
            for match in re.finditer(pattern, source, re.IGNORECASE):
                groups = match.groups()
                if len(groups) >= 2:
                    field_obj = ScreenField(
                        name=groups[0] if not groups[0].isdigit() else groups[2],
                        field_type=groups[1] if groups[1] in ('INPUT', 'OUTPUT', 'BOTH', 'I/O') else 'input',
                    )
                    fields.append(field_obj)
        
        # Also look for ACCEPT/DISPLAY fields as screen indicators
        accept_fields = re.findall(r'ACCEPT\s+([\w-]+)', source, re.IGNORECASE)
        display_fields = re.findall(r'DISPLAY\s+([\w-]+)', source, re.IGNORECASE)
        
        existing_names = {f.name for f in fields}
        for name in accept_fields:
            if name not in existing_names and not name.startswith(('WS-', 'ws-')):
                fields.append(ScreenField(name=name, field_type="input"))
                existing_names.add(name)
        for name in display_fields:
            if name not in existing_names and not name.startswith(('WS-', 'ws-')):
                fields.append(ScreenField(name=name, field_type="output"))
                existing_names.add(name)

        return fields

    def _extract_error_messages(self, source: str) -> list[ErrorMessage]:
        messages = []
        # Match string literals that look like error messages
        patterns = [
            r"(?:MOVE|DISPLAY|STRING)\s+'([^']*(?:ERROR|INVALID|REQUIRED|FAILED|NOT FOUND|ALREADY EXISTS)[^']*)'\s+TO\s+([\w-]+)",
            r"(?:MOVE|DISPLAY|STRING)\s+\"([^\"]*(?:ERROR|INVALID|REQUIRED|FAILED|NOT FOUND|ALREADY EXISTS)[^\"]*)\"",
            r"(?:MOVE|DISPLAY)\s+'([^']{10,})'\s+TO\s+(?:[\w-]*MSG[\w-]*|[\w-]*ERR[\w-]*|[\w-]*MESSAGE[\w-]*)",
            r"(?:MOVE|DISPLAY)\s+\"([^\"]{10,})\"\s+TO\s+(?:[\w-]*MSG[\w-]*|[\w-]*ERR[\w-]*|[\w-]*MESSAGE[\w-]*)",
            # Catch all quoted strings moved to message fields
            r"MOVE\s+'([^']+)'\s+TO\s+\w*(?:MSG|ERR|MESSAGE)\w*",
            r"MOVE\s+\"([^\"]+)\"\s+TO\s+\w*(?:MSG|ERR|MESSAGE)\w*",
        ]
        
        seen = set()
        for pattern in patterns:
            for match in re.finditer(pattern, source, re.IGNORECASE):
                msg_text = match.group(1).strip()
                if msg_text and msg_text not in seen:
                    seen.add(msg_text)
                    messages.append(ErrorMessage(
                        identifier=f"MSG-{len(messages)+1}",
                        message_text=msg_text,
                        context=match.group(0)[:100],
                    ))
        return messages

    def _extract_db_operations(self, source: str) -> list[DatabaseOperation]:
        operations = []
        # SQL operations
        sql_patterns = [
            (r'EXEC\s+SQL\s+SELECT\s+(.+?)\s+FROM\s+([\w-]+)', 'SELECT'),
            (r'EXEC\s+SQL\s+INSERT\s+INTO\s+([\w-]+)', 'INSERT'),
            (r'EXEC\s+SQL\s+UPDATE\s+([\w-]+)', 'UPDATE'),
            (r'EXEC\s+SQL\s+DELETE\s+FROM\s+([\w-]+)', 'DELETE'),
        ]
        for pattern, op_type in sql_patterns:
            for match in re.finditer(pattern, source, re.IGNORECASE | re.DOTALL):
                table = match.group(2) if op_type == 'SELECT' else match.group(1)
                operations.append(DatabaseOperation(
                    operation_type=op_type,
                    table_or_file=table.strip(),
                ))

        # File I/O operations
        file_patterns = [
            (r'READ\s+([\w-]+)', 'READ'),
            (r'WRITE\s+([\w-]+)', 'WRITE'),
            (r'REWRITE\s+([\w-]+)', 'REWRITE'),
            (r'DELETE\s+([\w-]+)\s+RECORD', 'DELETE'),
        ]
        for pattern, op_type in file_patterns:
            for match in re.finditer(pattern, source, re.IGNORECASE):
                operations.append(DatabaseOperation(
                    operation_type=op_type,
                    table_or_file=match.group(1).strip(),
                ))
        return operations

    def _extract_validations(self, source: str) -> list[Validation]:
        validations = []
        patterns = [
            (r'IF\s+([\w-]+)\s+(?:IS\s+)?NOT\s+NUMERIC', 'NUMERIC'),
            (r'IF\s+([\w-]+)\s+(?:IS\s+)?NUMERIC', 'NUMERIC'),
            (r'IF\s+([\w-]+)\s*=\s*SPACES', 'NOT_EMPTY'),
            (r'IF\s+([\w-]+)\s*=\s*ZEROES', 'NOT_ZERO'),
            (r'IF\s+([\w-]+)\s*=\s*LOW-VALUES', 'NOT_EMPTY'),
            (r'IF\s+(?:LENGTH|FUNCTION\s+LENGTH)\s*\(\s*([\w-]+)\s*\)\s*[<>]=?\s*(\d+)', 'LENGTH'),
            (r'IF\s+([\w-]+)\s*>\s*(\d+)', 'RANGE'),
            (r'IF\s+([\w-]+)\s*<\s*(\d+)', 'RANGE'),
        ]
        
        for pattern, val_type in patterns:
            for match in re.finditer(pattern, source, re.IGNORECASE):
                validations.append(Validation(
                    field_name=match.group(1),
                    validation_type=val_type,
                    condition=match.group(0).strip(),
                ))
        return validations

    def _extract_copybooks(self, source: str) -> list[str]:
        copies = re.findall(r'COPY\s+([\w-]+)', source, re.IGNORECASE)
        return list(set(copies))

    def _extract_file_definitions(self, source: str) -> list[str]:
        fds = re.findall(r'FD\s+([\w-]+)', source, re.IGNORECASE)
        selects = re.findall(r'SELECT\s+([\w-]+)\s+ASSIGN', source, re.IGNORECASE)
        return list(set(fds + selects))

    def get_summary(self, program: ParsedCobolProgram) -> dict:
        """Get a summary of parsed elements for reporting."""
        return {
            "program_id": program.program_id,
            "total_fields": len(program.working_storage_fields),
            "total_paragraphs": len(program.paragraphs),
            "total_screen_fields": len(program.screen_fields),
            "total_error_messages": len(program.error_messages),
            "total_db_operations": len(program.db_operations),
            "total_validations": len(program.validations),
            "copybooks": program.copybooks,
            "paragraph_names": [p.name for p in program.paragraphs],
            "screen_field_names": [f.name for f in program.screen_fields],
            "error_message_texts": [m.message_text for m in program.error_messages],
            "db_tables": list(set(op.table_or_file for op in program.db_operations)),
            "validation_fields": [v.field_name for v in program.validations],
        }
