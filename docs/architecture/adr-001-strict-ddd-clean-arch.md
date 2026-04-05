# ADR-001: Adopt Full Clean Architecture + DDD with Strict Dependency Rule

## Status
Accepted

## Context
Synapse-Desktop is a complex AI-assisted tool with evolving features (Smart Context, Semantic Index, Plugins). The current architecture uses DDD principles but has some coupling issues:
- `ServiceContainer` (Application Layer) imports from `Presentation` and `Infrastructure`.
- Business logic is sometimes leaked into services rather than dedicated domain entities.
- Lack of strict boundary enforcement leads to "spaghetti" dependencies as complexity grows.
- Personal tool for the developer, requiring high maintainability and ease of debugging.

## Decision
We will transition to a **Strict Clean Architecture** combined with **Domain-Driven Design (DDD)**. 

### Key Principles:
1. **The Dependency Rule**: Source code dependencies MUST only point inwards.
   - `Domain` (Inner) <- `Application` <- `Infrastructure` / `Presentation` (Outer).
2. **Domain Layer**: Contains Entities, Aggregates, Value Objects, and Domain Service Interfaces. NO dependencies on other layers.
3. **Application Layer**: Contains Use Case Handlers. It defines interfaces (Ports) for external resources (Repositories, Services). It only depends on the Domain.
4. **Infrastructure Layer**: Contains Adapters (concrete implementations of Repositories, API clients, etc.). It depends on Application (to implement ports) and Domain (to handle data models).
5. **Presentation Layer**: PySide6 UI. It uses the Application Layer services to trigger actions.
6. **Composition Root**: The initialization logic (Dependency Injection) will be moved to the outermost layer (e.g., `main_window.py` or a dedicated `infrastructure/di/` module).

## Rationale
- **Ease of Testing**: Decoupling the domain logic from the UI and disk/network allows for comprehensive unit testing without mocks for every small thing.
- **Ease of Refactoring**: We can swap out the database, the git engine, or even the UI library without touching the core business logic.
- **Maintainability**: Clear boundaries make it easier to understand where a bug resides (UI logic vs. Business rule).

## Trade-offs
- **Complexity**: Adds more boilerplate (Interfaces/Ports, Adapters, DTO mappings).
- **Learning Curve**: Requires strict discipline to not take "shortcuts" (e.g., importing a UI constant into a service).
- **Initial Cost**: Moving the entire codebase takes time and effort.

## Consequences
- **Positive**: High code quality (`pyrefly` strict mode), modularity, and future-proofing.
- **Negative**: Increased file count and potential for mapping overhead.
- **Mitigation**: Use simple Pydantic models for DTOs and a lightweight DI container.

## Revisit Trigger
- If the project remains small and the indirection becomes a significant development bottleneck.
