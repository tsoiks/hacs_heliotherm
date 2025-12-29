# Architecture Decision Records (ADRs)

This directory contains Architecture Decision Records documenting key design decisions for the Heliotherm component.

## What is an ADR?

An ADR is a document that records an important architectural decision, including:
- **Context**: The situation that motivated the decision
- **Decision**: What we decided to do
- **Consequences**: The implications and tradeoffs

ADRs are immutable once decided. New decisions that overturn old ones create new ADRs.

## Current ADRs

1. **[ADR-001: Use Coordinator Pattern for Data Management](001-coordinator-pattern.md)**
   - Centralized data fetching and caching via `DataUpdateCoordinator`
   - Prevents duplicate API calls and ensures single source of truth

2. **[ADR-002: Read-Only vs. Write Mode Configuration](002-read-only-vs-write-mode.md)**
   - Component supports both read-only and read-write operation modes
   - Read-only mode creates only sensors; write mode adds switches and climate entities

3. **[ADR-003: Modbus Register Abstraction](003-modbus-abstraction.md)**
   - All Modbus operations abstracted in coordinator
   - Register mappings centralized in constants

4. **[ADR-004: Entity Design and Configuration](004-entity-design.md)**
   - Entities defined declaratively using `EntityDescription` objects
   - Configuration-driven entity creation based on feature flags

## Reading an ADR

Start with [ADR-001](001-coordinator-pattern.md) to understand the foundation, then explore others as needed.

## When to Create a New ADR

Create an ADR when:
- Making a significant architectural decision
- Choosing between multiple design approaches
- Documenting assumptions about system behavior
- Reversing a previous decision (create new ADR, don't modify old one)

## ADR Template

See [ADR-000: ADR Template](000-template.md) for the standard format.
