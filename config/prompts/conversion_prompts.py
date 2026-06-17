"""Prompt templates for COBOL/Telon to Spring Boot + Next.js conversion."""

SYSTEM_PROMPT = """You are an expert mainframe modernization architect specializing in converting 
COBOL/Telon applications to modern Spring Boot (Java) backend and Next.js (TypeScript/React) frontend.

You must produce production-ready, well-structured, MODULAR code that preserves ALL business logic, 
error handling, validations, and data operations from the original COBOL/Telon source.

CRITICAL MODULARITY RULES:
- Backend: Follow clean layered Spring Boot architecture (controller → service → repository → entity).
  Each layer in its own package. Never put business logic in controllers. Never put DB access in services directly.
- Frontend: Follow Next.js App Router conventions with reusable components, custom hooks, API service layer,
  and separated validation schemas. Use shadcn/ui components exclusively.
- Each class/component should have a single responsibility.
- Shared logic goes in utils/helpers. Constants in dedicated files.
"""

INITIAL_CONVERSION_PROMPT = """Analyze the following COBOL/Telon source code and convert it into a fully 
modular, production-ready application with Spring Boot backend and Next.js frontend.

## COBOL/Telon Source Code:
```
{source_code}
```

---

## SPRING BOOT BACKEND — Generate ALL of the following layers:

### 1. Entity Layer (`com.app.entity`)
- One JPA entity per COPYBOOK/record structure
- Map PIC X(n) → String, PIC 9(n) → Long/Integer, PIC 9(n)V99 → BigDecimal
- Include @Entity, @Table, @Id, @Column annotations with proper column names/lengths
- Add @CreatedDate, @LastModifiedDate where applicable

### 2. Repository Layer (`com.app.repository`)
- One Spring Data JPA repository per entity
- Map COBOL READ with key → findById or custom findBy methods
- Map COBOL READ with conditions → custom @Query methods
- Map WRITE → save, REWRITE → save, DELETE → deleteById

### 3. DTO Layer (`com.app.dto`)
- Separate Request DTOs (for incoming data) and Response DTOs (for outgoing data)
- Include Jakarta Bean Validation annotations (@NotBlank, @Size, @Pattern, @NotNull, etc.)
  matching EVERY validation from the original COBOL code
- Add a generic ApiResponse<T> wrapper DTO for consistent API responses

### 4. Mapper/Converter (`com.app.mapper`)
- Entity ↔ DTO mapping methods (or use MapStruct interface)
- Keep mapping logic separate from service layer

### 5. Service Layer (`com.app.service`)
- Interface + Implementation pattern (e.g., CustomerService + CustomerServiceImpl)
- ALL business logic from COBOL paragraphs goes here
- Each COBOL paragraph/section → one Java method
- Preserve ALL EVALUATE/IF conditions as equivalent Java logic
- Preserve ALL PERFORM loops as Java iterations
- Service calls repository (never accesses DB directly)
- Throws custom exceptions for error conditions

### 6. Validator Layer (`com.app.validator`)
- Custom validation classes for complex business rules that go beyond simple annotations
- E.g., cross-field validation, conditional required fields, status code checks
- Implement Spring's Validator interface or use custom @Constraint annotations

### 7. Exception Layer (`com.app.exception`)
- Custom exception classes for each error type (e.g., ResourceNotFoundException, 
  DuplicateRecordException, ValidationException)
- Global @RestControllerAdvice exception handler that maps exceptions to proper HTTP responses
- Preserve ALL error messages exactly as they appear in the COBOL source
- Include an ErrorResponse DTO

### 8. Controller Layer (`com.app.controller`)
- REST controllers with proper HTTP methods (GET, POST, PUT, DELETE)
- @Valid on request DTOs for validation
- Controllers only delegate to service layer — NO business logic here
- Proper @RequestMapping, @PathVariable, @RequestBody annotations
- Return ResponseEntity with ApiResponse wrapper

### 9. Config Layer (`com.app.config`)
- CORS configuration for Next.js frontend
- Any application.yml/properties settings needed

### 10. Utility Layer (`com.app.util`)
- Constants class for any hardcoded values, status codes, magic strings from COBOL
- Helper methods for common operations (date formatting, string padding, etc.)

---

## NEXT.JS FRONTEND (App Router + shadcn/ui) — Generate ALL of the following:

### 1. Types/Interfaces (`src/types/`)
- TypeScript interfaces matching backend DTOs
- Separate files per domain (e.g., customer.types.ts, api.types.ts)

### 2. API Service Layer (`src/services/` or `src/lib/api/`)
- Centralized API client (axios or fetch wrapper)
- One service file per domain with typed request/response functions
- E.g., customerService.ts: getCustomer(), createCustomer(), updateCustomer(), deleteCustomer()
- Handle API errors consistently

### 3. Validation Schemas (`src/lib/validations/`)
- Zod schemas matching EVERY field validation from the original COBOL code
- One schema file per form/domain
- Reuse schemas between client and server-side validation

### 4. Custom Hooks (`src/hooks/`)
- useForm hooks wrapping react-hook-form + zod resolver for each form
- Data fetching hooks (e.g., useCustomer, useCustomerList)
- Toast/notification hooks

### 5. Reusable UI Components (`src/components/`)
- Built exclusively with shadcn/ui components
- Form field wrapper components (FormField with Label + Input + error message)
- Data display components (detail cards, data tables)
- Confirmation dialog component
- Loading/error state components

### 6. Feature Components (`src/components/features/[feature-name]/`)
- Feature-specific composed components (e.g., CustomerForm, CustomerTable, CustomerDetail)
- Each component is self-contained with its own state management

### 7. Page Components (`src/app/[route]/page.tsx`)
- Next.js App Router pages
- Pages compose feature components — minimal logic in pages
- Proper loading.tsx and error.tsx for each route

### 8. Constants (`src/lib/constants/`)
- UI labels, status mappings, error message strings
- Route paths

---

## Requirements:
- Preserve EVERY paragraph/section as equivalent Java service methods
- Map ALL COPYBOOK/working storage fields to Java entities/DTOs
- Convert ALL EVALUATE/IF conditions to equivalent Java logic
- Map ALL screen fields to shadcn/ui React form components
- Preserve ALL error messages exactly as they appear in the source
- Map ALL file/DB operations (READ, WRITE, REWRITE, DELETE) to JPA repository calls
- Convert ALL PERFORM loops to Java iterations
- Preserve field-level validations (NUMERIC checks, length checks, required fields)
  in BOTH backend (Jakarta annotations + custom validators) AND frontend (zod schemas)
- Use shadcn/ui components for ALL UI elements (no plain HTML inputs/buttons)
- Import shadcn components from "@/components/ui/[component]"

## Output Format:
Return the code in clearly separated sections with file paths as headers.
Generate EVERY file listed below (adapt names to match the program being converted):

### FILE: src/main/java/com/app/entity/[EntityName].java
### FILE: src/main/java/com/app/repository/[EntityName]Repository.java
### FILE: src/main/java/com/app/dto/request/[EntityName]Request.java
### FILE: src/main/java/com/app/dto/response/[EntityName]Response.java
### FILE: src/main/java/com/app/dto/response/ApiResponse.java
### FILE: src/main/java/com/app/mapper/[EntityName]Mapper.java
### FILE: src/main/java/com/app/service/[EntityName]Service.java
### FILE: src/main/java/com/app/service/impl/[EntityName]ServiceImpl.java
### FILE: src/main/java/com/app/validator/[EntityName]Validator.java
### FILE: src/main/java/com/app/exception/ResourceNotFoundException.java
### FILE: src/main/java/com/app/exception/DuplicateRecordException.java
### FILE: src/main/java/com/app/exception/GlobalExceptionHandler.java
### FILE: src/main/java/com/app/exception/ErrorResponse.java
### FILE: src/main/java/com/app/controller/[EntityName]Controller.java
### FILE: src/main/java/com/app/config/CorsConfig.java
### FILE: src/main/java/com/app/util/AppConstants.java
### FILE: src/main/resources/application.yml
### FILE: src/types/[entity].types.ts
### FILE: src/types/api.types.ts
### FILE: src/services/[entity]Service.ts
### FILE: src/services/apiClient.ts
### FILE: src/lib/validations/[entity].schema.ts
### FILE: src/hooks/use[Entity]Form.ts
### FILE: src/hooks/use[Entity].ts
### FILE: src/components/features/[entity]/[Entity]Form.tsx
### FILE: src/components/features/[entity]/[Entity]Table.tsx
### FILE: src/components/features/[entity]/[Entity]Detail.tsx
### FILE: src/app/[entity]/page.tsx
### FILE: src/app/[entity]/loading.tsx
### FILE: src/app/[entity]/error.tsx
### FILE: src/lib/constants/index.ts
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
Fix ALL the identified gaps while maintaining the MODULAR STRUCTURE:

### Backend modularity checks:
1. Business logic ONLY in service layer (not in controllers)
2. DB access ONLY through repositories (not direct in services)
3. Separate Request and Response DTOs
4. Custom validators for complex validation rules
5. Global exception handler with custom exception classes
6. Entity ↔ DTO mapping in dedicated mapper class
7. Constants/utils for shared values

### Frontend modularity checks:
1. API calls ONLY through service layer (not in components)
2. Form logic in custom hooks (not inline in components)
3. Zod validation schemas in dedicated files
4. Feature components composed from shadcn/ui primitives
5. Pages only compose feature components — no direct logic
6. Types/interfaces in dedicated type files

### For each gap:
1. Add the missing business logic, validation, or field
2. Ensure error messages match exactly
3. Ensure DB operations map correctly to the schema
4. Ensure UI fields use shadcn/ui components
5. Ensure form validations use react-hook-form + zod

IMPORTANT: EVERY dimension must individually score >= 95%. The iteration will continue
until ALL dimensions pass this threshold. Focus on the lowest-scoring dimensions first.

Return the COMPLETE corrected code (not just the fixes) in the same file-path format.
"""
