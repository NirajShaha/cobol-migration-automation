"""Prompt templates for analyzing migration accuracy."""

ANALYSIS_SYSTEM_PROMPT = """You are a strict code migration quality auditor. Your job is to compare 
original COBOL/Telon code against migrated Spring Boot + Next.js code and identify EVERY gap, 
missing feature, or incorrect implementation. Be thorough and precise."""

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
- List each COBOL paragraph/section and whether it has an equivalent Java method
- Check EVALUATE/IF statement logic is correctly translated
- Check PERFORM loop logic is correctly translated
- Check COMPUTE/arithmetic operations are correct

### 2. Error Handling (score: X/100)
- List each error condition in COBOL and whether it's handled in Java
- Check exception types are appropriate
- Check error flow (GOTO, PERFORM after error) is preserved

### 3. Schema & Table Mapping (score: X/100)
- List each COPYBOOK/file definition and its entity/DTO mapping
- Check field types match (PIC X -> String, PIC 9 -> Integer/Long, etc.)
- Check table names and relationships are correct
- Check CRUD operations match (READ->findBy, WRITE->save, DELETE->delete, REWRITE->save)

### 4. Field Validations (score: X/100)
- List each validation in COBOL (NUMERIC check, SPACES check, length check)
- Check if equivalent validation exists in Java service/DTO annotations
- Check if client-side validation exists in Next.js

### 5. UI Fields (score: X/100)
- List each screen field from Telon definition
- Check if corresponding React form field exists
- Check field types (input, dropdown, checkbox, etc.) match
- Check field labels and positioning

### 6. Error Messages (score: X/100)
- List each error message literal in the COBOL source
- Check if same message appears in Java exception/response
- Check if message is displayed in Next.js UI

## Output Format (STRICT JSON):
```json
{{
    "overall_score": <weighted_average>,
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
