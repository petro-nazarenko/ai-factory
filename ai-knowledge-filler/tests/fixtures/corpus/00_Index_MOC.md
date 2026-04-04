---
title: AI Solutions Architect OS — Master Map of Content
type: reference
domain: ontology
level: advanced
status: active
version: v1.0
tags:
  - map-of-content
  - navigation
  - index
  - orchestration
  - expert-system
related:
  - "[[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/Ontology_Governance_for_AI_Generated_Knowledge_Bases|part-of]]"
  - "[[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/Knowledge_Management_Architecture|references]]"
  - "[[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/Obsidian_Vault_Structure_for_AI_Workflows|references]]"
created: 2026-03-17
updated: 2026-03-17
---

## Purpose

Master Map of Content for the AI Solutions Architect SOP Library. Use this file as the single entry point to navigate 47 knowledge files organized by domain, type, and project lifecycle phase. Thin spots and evolution roadmap are documented in the Gap Analysis section.

---

## Domain Registry

### `#ai-system` — LLM Engineering & AI Pipelines

#### `#concept`
- [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/Chain_of_Thought_Reasoning_in_AI_Agents]] — Structured reasoning patterns for agentic LLM workflows
- [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/Ontology_Governance_for_AI_Generated_Knowledge_Bases]] — Governance models for AI-produced knowledge taxonomies

#### `#guide`
- [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/Deterministic_Retry_Logic_in_LLM_Pipelines]] — Convergence-safe retry patterns for LLM generation loops
- [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/Obsidian_Vault_Structure_for_AI_Workflows]] — Vault design for AI-assisted knowledge management
- [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/Prompt_Engineering_Techniques_for_Structured_Output]] — Techniques for eliciting reliable structured LLM output
- [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/Schema_as_Contract_Pattern_for_Structured_AI_Output]] — Schema-first design enforcing output contracts

#### `#reference`
- [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/LLM_Context_Window_Management]] — Strategies for managing token budgets and context across long sessions
- [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/LLM_Output_Validation_Pipeline_Architecture]] — End-to-end validation architecture for LLM-generated content

#### `#checklist`
- [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/AI_Pipeline_Reliability_Audit_Checklist]] — Pre-production reliability gate for LLM pipelines

---

### `#api-design` — API Contracts & Documentation

#### `#concept`
- [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/GraphQL_vs_REST_API_Design_Trade_offs]] — Decision framework for choosing GraphQL vs REST

#### `#reference`
- [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/API_Documentation_Structure_OpenAPI]] — OpenAPI 3.1 spec structure and documentation standards
- [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/REST_API_Versioning_Strategies]] — Approaches to versioning APIs without breaking clients

---

### `#backend-engineering` — Service Architecture & Python Backend

#### `#guide`
- [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/API_Rate_Limiting_with_FastAPI]] — Rate limiting patterns for FastAPI services
- [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/Python_Packaging_Best_Practices]] — Packaging, build, and distribution for Python projects
- [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/Workflow_Automation_Design_Python_Webhooks]] — Webhook-driven automation pipelines in Python

#### `#reference`
- [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/Backend_Service_Architecture_FastAPI]] — Production-grade FastAPI service architecture
- [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/Backend_API_Production_Readiness_Checklist]] — Pre-launch production readiness checklist

#### `#checklist`
- [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/Backend_API_Production_Readiness_Checklist]] — Complete readiness gate for API services

---

### `#business-strategy` — GTM & Market Intelligence

#### `#concept` / `#reference`
- [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/No_Code_Integration_Patterns]] — No-code/low-code integration strategies for SaaS products
- [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/Competitive_Analysis_Framework_AI_Developer_Tools]] — Structured competitive analysis for AI tooling

#### `#guide`
- [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/Go_to_Market_Strategy_Open_Source_Tools]] — GTM playbook for open-source developer tools

---

### `#consulting` — Client Engagement & Deliverables

#### `#concept`
- [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/AI_Consulting_Engagement_Framework]] — End-to-end engagement model for AI consulting projects

#### `#reference`
- [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/Consulting_Deliverable_Standards]] — Standards and formats for consulting deliverables

---

### `#data-engineering` — Data Pipelines & Modeling

#### `#concept`
- [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/Stream_Processing_vs_Batch_Processing]] — Trade-off analysis between streaming and batch data architectures

#### `#guide`
- [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/ETL_Pipeline_Design_for_Data_Warehousing]] — ETL design patterns for modern data warehouses

#### `#reference`
- [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/Data_Modeling_Patterns_Analytical_Databases]] — Dimensional and analytical modeling patterns

---

### `#devops` — Infrastructure, CI/CD & Cloud

#### `#guide`
- [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/CICD_Pipeline_Design_GitHub_Actions]] — GitHub Actions-based CI/CD pipeline design
- [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/Observability_Stack_Design]] — Observability architecture with metrics, logs, and traces

#### `#reference`
- [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/Cloud_Infrastructure_Cost_Optimization_AWS]] — AWS cost optimization strategies and tooling
- [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/Docker_Multi_Stage_Builds]] — Multi-stage Docker build patterns for minimal production images

#### `#checklist`
- [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/Kubernetes_Deployment_Readiness_Checklist]] — Kubernetes deployment gates and readiness checks

---

### `#frontend-engineering` — UI & Performance

#### `#concept`
- [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/Web_Performance_Optimization_Strategies]] — Core Web Vitals and frontend performance strategies

#### `#guide`
- [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/React_Component_Architecture_Patterns]] — Component design patterns for scalable React applications

---

### `#machine-learning` — ML Engineering

#### `#guide`
- [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/ML_Model_Deployment_Patterns]] — Deployment patterns for ML models (batch, real-time, shadow mode)

#### `#reference`
- [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/Feature_Engineering_Best_Practices]] — Feature selection, transformation, and pipeline design

---

### `#product-management` — Roadmap, Requirements & Documentation

#### `#guide`
- [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/Technical_Documentation_Standards]] — Standards for technical writing and documentation
- [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/Technical_Product_Requirements_Documents]] — PRD structure for technical product features

#### `#reference`
- [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/Product_Roadmap_Prioritization_Frameworks]] — RICE, ICE, MoSCoW, and Kano prioritization methods

---

### `#project-management` — Agile & Risk

#### `#guide`
- [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/Agile_Project_Management_Solo_Developers]] — Personal Kanban and solo Agile practices

#### `#reference`
- [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/Risk_Management_Software_Projects]] — Risk identification, scoring, and mitigation frameworks

---

### `#security` — Auth, Threat Modeling & Zero Trust

#### `#concept`
- [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/Zero_Trust_Architecture_Principles]] — Never-trust, always-verify security model

#### `#guide`
- [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/OAuth_2_Implementation_for_API_Authentication]] — OAuth 2.0 flows for API authentication

#### `#checklist`
- [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/Application_Security_Checklist_REST_APIs]] — OWASP-aligned security checklist for REST APIs

---

### `#system-design` — Architecture Patterns & Knowledge Systems

#### `#concept`
- [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/CAP_Theorem_and_Distributed_Consistency]] — Consistency vs availability trade-offs in distributed systems
- [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/Knowledge_Management_Architecture]] — Architecture patterns for organizational knowledge systems

#### `#guide`
- [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/Event_Driven_Architecture_Design]] — Event-driven design patterns and messaging topologies

#### `#reference`
- [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/Microservices_Architecture_Patterns]] — Service decomposition, communication, and resilience patterns
- [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/Personal_Knowledge_Management_System_Design]] — PKM system design for knowledge workers

---

## Lifecycle View

Files arranged in the order they are typically needed across a consulting or build engagement.

### 1. DISCOVERY — Understand the Problem Space

| File | Purpose |
|------|---------|
| [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/AI_Consulting_Engagement_Framework]] | Frame the engagement, scope client problem |
| [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/Competitive_Analysis_Framework_AI_Developer_Tools]] | Map the competitive landscape |
| [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/Product_Roadmap_Prioritization_Frameworks]] | Prioritize what to build |
| [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/Technical_Product_Requirements_Documents]] | Define functional and non-functional requirements |
| [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/Risk_Management_Software_Projects]] | Identify and score project risks early |

### 2. DESIGN — Architect the Solution

| File | Purpose |
|------|---------|
| [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/Backend_Service_Architecture_FastAPI]] | Choose service architecture patterns |
| [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/API_Documentation_Structure_OpenAPI]] | Define the API contract |
| [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/Schema_as_Contract_Pattern_for_Structured_AI_Output]] | Establish AI output contracts |
| [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/LLM_Output_Validation_Pipeline_Architecture]] | Design the validation pipeline |
| [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/Microservices_Architecture_Patterns]] | Decompose services |
| [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/Event_Driven_Architecture_Design]] | Design async communication |
| [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/CAP_Theorem_and_Distributed_Consistency]] | Choose consistency model |
| [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/Knowledge_Management_Architecture]] | Design knowledge layer if needed |
| [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/Zero_Trust_Architecture_Principles]] | Apply security principles from the start |

### 3. BUILD — Implement the System

| File | Purpose |
|------|---------|
| [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/Prompt_Engineering_Techniques_for_Structured_Output]] | Write generation prompts |
| [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/Chain_of_Thought_Reasoning_in_AI_Agents]] | Implement agent reasoning |
| [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/Deterministic_Retry_Logic_in_LLM_Pipelines]] | Build retry and convergence logic |
| [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/LLM_Context_Window_Management]] | Manage token budgets |
| [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/API_Rate_Limiting_with_FastAPI]] | Implement rate limiting |
| [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/OAuth_2_Implementation_for_API_Authentication]] | Implement auth flows |
| [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/REST_API_Versioning_Strategies]] | Version the API |
| [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/GraphQL_vs_REST_API_Design_Trade_offs]] | Finalize API design decisions |
| [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/React_Component_Architecture_Patterns]] | Build frontend components |
| [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/Feature_Engineering_Best_Practices]] | Prepare ML features |
| [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/ML_Model_Deployment_Patterns]] | Productionize ML models |
| [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/ETL_Pipeline_Design_for_Data_Warehousing]] | Build data pipelines |
| [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/Stream_Processing_vs_Batch_Processing]] | Choose processing paradigm |
| [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/Data_Modeling_Patterns_Analytical_Databases]] | Model the data layer |
| [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/Workflow_Automation_Design_Python_Webhooks]] | Automate operational workflows |
| [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/No_Code_Integration_Patterns]] | Integrate no-code components |
| [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/Docker_Multi_Stage_Builds]] | Containerize services |
| [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/Python_Packaging_Best_Practices]] | Package Python libraries |

### 4. DEPLOY — Deliver to Production

| File | Purpose |
|------|---------|
| [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/CICD_Pipeline_Design_GitHub_Actions]] | Automate build, test, and deploy |
| [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/Kubernetes_Deployment_Readiness_Checklist]] | Gate Kubernetes deployments |
| [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/Cloud_Infrastructure_Cost_Optimization_AWS]] | Optimize cloud spend |
| [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/Observability_Stack_Design]] | Wire metrics, logs, and traces |
| [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/Backend_API_Production_Readiness_Checklist]] | Final pre-launch gate |
| [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/Application_Security_Checklist_REST_APIs]] | Security review before go-live |
| [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/Web_Performance_Optimization_Strategies]] | Optimize frontend performance |

### 5. AUDIT — Review & Improve

| File | Purpose |
|------|---------|
| [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/AI_Pipeline_Reliability_Audit_Checklist]] | Audit LLM pipeline reliability |
| [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/Consulting_Deliverable_Standards]] | Review deliverable quality |
| [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/Ontology_Governance_for_AI_Generated_Knowledge_Bases]] | Govern the knowledge taxonomy |
| [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/Technical_Documentation_Standards]] | Audit documentation quality |
| [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/Personal_Knowledge_Management_System_Design]] | Improve PKM practices |
| [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/Obsidian_Vault_Structure_for_AI_Workflows]] | Optimize vault structure |
| [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/Agile_Project_Management_Solo_Developers]] | Retrospect and improve delivery |
| [[Claude/projects/ai-factory/ai-knowledge-filler/tests/fixtures/corpus/Go_to_Market_Strategy_Open_Source_Tools]] | Review GTM execution |

---

## Gap Analysis

### Thin Spots — Broken WikiLinks

The following internal links reference files that do not exist in the corpus. These represent either truncated link names or genuinely missing knowledge:

| Broken Link | Likely Referencing | Action |
|-------------|-------------------|--------|
| `[[AI_Pipeline_Reliability_Audit]]` | `AI_Pipeline_Reliability_Audit_Checklist.md` | Rename link (truncation) |
| `[[Application_Security_Checklist]]` | `Application_Security_Checklist_REST_APIs.md` | Rename link (truncation) |
| `[[Backend_API_Production_Readiness]]` | `Backend_API_Production_Readiness_Checklist.md` | Rename link (truncation) |
| `[[Chain_of_Thought_Reasoning]]` | `Chain_of_Thought_Reasoning_in_AI_Agents.md` | Rename link (truncation) |
| `[[Deterministic_Retry_Logic]]` | `Deterministic_Retry_Logic_in_LLM_Pipelines.md` | Rename link (truncation) |
| `[[ETL_Pipeline_Design]]` | `ETL_Pipeline_Design_for_Data_Warehousing.md` | Rename link (truncation) |
| `[[Kubernetes_Deployment_Readiness]]` | `Kubernetes_Deployment_Readiness_Checklist.md` | Rename link (truncation) |
| `[[OAuth_2_Implementation]]` | `OAuth_2_Implementation_for_API_Authentication.md` | Rename link (truncation) |
| `[[Obsidian_Vault_Structure]]` | `Obsidian_Vault_Structure_for_AI_Workflows.md` | Rename link (truncation) |
| `[[Prompt_Engineering_Techniques]]` | `Prompt_Engineering_Techniques_for_Structured_Output.md` | Rename link (truncation) |
| `[[Schema_as_Contract_Pattern]]` | `Schema_as_Contract_Pattern_for_Structured_AI_Output.md` | Rename link (truncation) |
| `[[Domain_Taxonomy]]` | No matching file | **Genuinely missing** |

### Suggested Next Files

Three files that would bridge the gap between `Product_Roadmap_Prioritization_Frameworks` and `LLM_Output_Validation_Pipeline_Architecture`:

#### 1. `AI_Product_Feature_Specification.md`
**Domain:** `product-management` | **Type:** `template`

Bridges the translation gap between product roadmap items and LLM system requirements. Covers: AI-specific acceptance criteria, prompt contract definition, model selection criteria, output quality gates, and latency SLAs. Connects `[[Product_Roadmap_Prioritization_Frameworks]]` → `[[LLM_Output_Validation_Pipeline_Architecture]]`.

#### 2. `LLM_Evaluation_and_Testing_Framework.md`
**Domain:** `ai-system` | **Type:** `guide`

Defines how to systematically test LLM-powered features before shipping. Covers: golden dataset construction, eval harness design, regression testing strategies, human-in-the-loop eval workflows, and automated quality metrics. Connects `[[Prompt_Engineering_Techniques_for_Structured_Output]]` → `[[LLM_Output_Validation_Pipeline_Architecture]]`.

#### 3. `AI_Readiness_Assessment_Checklist.md`
**Domain:** `consulting` | **Type:** `checklist`

Pre-engagement assessment for AI project readiness. Covers: stakeholder alignment, data availability audit, infrastructure readiness, model selection criteria, compliance and privacy review, and success metric definition. Connects `[[AI_Consulting_Engagement_Framework]]` → `[[ML_Model_Deployment_Patterns]]`.

---

## Template Index

Reusable project templates are maintained in `.templates/` at the repository root:

| Template | Source Files | Use When |
|----------|-------------|----------|
| [[New_Project_Checklist]] | `Agile_Project_Management_Solo_Developers` + `AI_Pipeline_Reliability_Audit_Checklist` | Kicking off any new build or consulting engagement |
| [[Service_Blueprint]] | `Backend_Service_Architecture_FastAPI` + `API_Documentation_Structure_OpenAPI` | Starting a new backend service or API |

---

## Conclusion

This MOC is the orchestration layer for the AI Solutions Architect OS. Navigate by domain for deep reference, by lifecycle phase for project execution, and by gap analysis for corpus evolution. Update this index whenever new files are added or existing files are promoted to `active` status.
