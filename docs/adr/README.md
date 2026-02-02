# Architecture Decision Records (ADR)

This directory contains Architecture Decision Records for the eZansi TTS Capability.

## What is an ADR?

An Architecture Decision Record (ADR) is a document that captures an important architectural decision made along with its context and consequences.

## Index

- [ADR-001: Hardware Detection and Dynamic Resource Configuration](001-hardware-detection-and-dynamic-resources.md) - Implements automatic hardware detection to replace static hardware profiles
- [ADR-002: Container Runtime, Engine Fallbacks, and Default Model Bootstrapping](002-container-runtime-and-model-management.md) - Standardizes container base image, startup semantics, model bootstrapping, and runtime discovery endpoints

## Format

Each ADR follows this structure:
- **Status**: Proposed, Accepted, Deprecated, Superseded
- **Date**: When the decision was made
- **Context**: The issue motivating this decision
- **Decision**: What was decided
- **Consequences**: Positive and negative outcomes
- **Alternatives Considered**: Other options that were evaluated
