"""Prompt templates for analyzing migration accuracy."""

ANALYSIS_SYSTEM_PROMPT = """You are a strict code migration quality auditor. Your job is to compare 
original COBOL/Telon code against migrated Spring Boot + Next.js code and identify EVERY gap, 
missing feature, or incorrect implementation. Be thorough and precise.

You must also verify the code follows proper modular architecture:
- Backend: controller → service → repository → entity (no layer skipping)
- Frontend: page → feature component → hook → service → API (proper separation)
- Validations in both backend (Jakarta + custom validators) and frontend (zod schemas)
- DTOs separate from entities, request DTOs separate from response DTOs"""

ACCURACY_ANALYSIS_PROMPT = """Compare the original COBOL/Telon source code against the migrated 
Spring Boot + Next.js code. Evaluate accuracy across these dimensions:

## Original COBOL/Telon Code:
```
{source_code}
```

## Migrated Code:
{migrated_code}

## Evaluate each dimension and provide a score (0-100) with specific findings:

### 1. Business Logic Coverage (score: X/100)
- List each COBOL paragraph/section and whether it has an equivalent Java SERVICE method
- Check EVALUATE/IF statement logic is correctly translated
- Check PERFORM loop logic is correctly translated
- Check COMPUTE/arithmetic operations are correct
- Verify business logic is in the service layer (NOT in controllers)
- Verify service uses interface + implementation pattern

### 2. Error Handling (score: X/100)
- List each error condition in COBOL and whether it's handled via custom exceptions in Java
- Check a GlobalExceptionHandler (@RestControllerAdvice) exists
- Check custom exception classes exist (ResourceNotFoundException, DuplicateRecordException, etc.)
- Check error flow (GOTO, PERFORM after error) is preserved
- Check ErrorResponse DTO is used for consistent error format

### 3. Schema & Table Mapping (score: X/100)
- List each COPYBOOK/file definition and its entity mapping
- Check field types match (PIC X → String, PIC 9 → Integer/Long, PIC 9V99 → BigDecimal)
- Check JPA annotations (@Entity, @Table, @Column with length/precision) are correct
- Check repository interface exists with proper query methods
- Check CRUD operations match (READ→findBy, WRITE→save, DELETE→delete, REWRITE→save)
- Check Request/Response DTOs are separate from entities
- Check mapper class exists for entity ↔ DTO conversion

### 4. Field Validations (score: X/100)
- List each validation in COBOL (NUMERIC check, SPACES check, length check)
- Check if equivalent Jakarta validation annotation exists on Request DTOs
- Check if custom validator class exists for complex business rules
- Check if equivalent Zod schema validation exists in frontend
- Check if validations exist in BOTH backend AND frontend

### 5. UI Fields (score: X/100)
- List each screen field from Telon definition
- Check if corresponding shadcn/ui form field exists in a feature component
- Check field types match (Input, Select, Checkbox, etc.)
- Check form uses react-hook-form with zod resolver
- Check API calls go through a service layer (not directly in components)
- Check feature components are composed (not monolithic)

### 6. Error Messages (score: X/100)
- List each error message literal in the COBOL source
- Check if same message appears in Java exception/service (via constants or inline)
- Check if message is displayed in Next.js via shadcn Alert/Toast components

## Output Format (STRICT JSON):
```json
{{
    "overall_score": <average_of_all_dimensions>,
    "dimensions": {{
        "business_logic": {{
            "score": <0-100>,
            "matched_items": ["item1", "item2"],
            "missing_items": ["missing1", "missing2"],
            "incorrect_items": ["incorrect1"]
        }},
        "error_handling": {{
            "score": <0-100>,
            "matched_items": [],
            "missing_items": [],
            "incorrect_items": []
        }},
        "schema_mapping": {{
            "score": <0-100>,
            "matched_items": [],
            "missing_items": [],
            "incorrect_items": []
        }},
        "field_validation": {{
            "score": <0-100>,
            "matched_items": [],
            "missing_items": [],
            "incorrect_items": []
        }},
        "ui_fields": {{
            "score": <0-100>,
            "matched_items": [],
            "missing_items": [],
            "incorrect_items": []
        }},
        "error_messages": {{
            "score": <0-100>,
            "matched_items": [],
            "missing_items": [],
            "incorrect_items": []
        }}
    }},
    "summary": "Brief summary of main gaps"
}}
```
"""
