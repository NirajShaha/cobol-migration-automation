"""Prompt templates for COBOL/Telon to Spring Boot + Next.js conversion."""

SYSTEM_PROMPT = """You are an expert mainframe modernization architect specializing in converting 
COBOL/Telon applications to modern Spring Boot (Java) backend and Next.js (TypeScript/React) frontend.

You must produce production-ready, well-structured code that preserves ALL business logic, 
error handling, validations, and data operations from the original COBOL/Telon source."""

INITIAL_CONVERSION_PROMPT = """Analyze the following COBOL/Telon source code and convert it into:
1. **Spring Boot (Java)** backend code - including:
   - Entity classes mapping to COPYBOOK structures
   - Repository interfaces for database operations
   - Service classes with ALL business logic preserved
   - Controller/REST API endpoints
   - DTOs for request/response
   - Exception handling matching original error flows
   - Input validations matching original field validations

2. **Next.js (TypeScript/React)** frontend code - including:
   - Page components matching Telon screens
   - Form fields matching ALL screen input/output fields
   - Client-side validations matching original field validations
   - API integration with the Spring Boot backend
   - Error message display matching original error messages
   - Proper TypeScript types/interfaces

## COBOL/Telon Source Code:
```
{source_code}
```

## Requirements:
- Preserve EVERY paragraph/section as equivalent Java methods
- Map ALL COPYBOOK/working storage fields to Java entities/DTOs
- Convert ALL EVALUATE/IF conditions to equivalent Java logic
- Map ALL screen fields to React form components
- Preserve ALL error messages exactly as they appear in the source
- Map ALL file/DB operations (READ, WRITE, REWRITE, DELETE) to JPA repository calls
- Convert ALL PERFORM loops to Java iterations
- Preserve field-level validations (NUMERIC checks, length checks, required fields)

## Output Format:
Return the code in clearly separated sections with file paths as headers:
### FILE: src/main/java/com/app/entity/[EntityName].java
### FILE: src/main/java/com/app/repository/[RepoName].java
### FILE: src/main/java/com/app/service/[ServiceName].java
### FILE: src/main/java/com/app/controller/[ControllerName].java
### FILE: src/main/java/com/app/dto/[DtoName].java
### FILE: src/main/java/com/app/exception/[ExceptionName].java
### FILE: src/app/[page-name]/page.tsx
### FILE: src/components/[ComponentName].tsx
### FILE: src/types/[types].ts
"""

REFINEMENT_PROMPT = """The previous conversion attempt scored {accuracy_score}% accuracy.
Below are the specific gaps identified:

## Accuracy Report:
{accuracy_report}

## Missing/Incorrect Items:
{missing_items}

## Original COBOL/Telon Source (for reference):
```
{source_code}
```

## Previously Generated Code:
{generated_code}

## Instructions:
Fix ALL the identified gaps. For each missing item:
1. Add the missing business logic, validation, or field
2. Ensure error messages match exactly
3. Ensure DB operations map correctly to the schema
4. Ensure UI fields match the original screen layout

Return the COMPLETE corrected code (not just the fixes) in the same file-path format.
"""
