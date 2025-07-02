# 🧭 Climate Document Pipeline – Future Steps

This file outlines the next key milestones planned for the development of the climate document ingestion and analysis pipeline. These are broad goals intended to guide the continued evolution of the project.

---

## 1. API Integration Refinement

Improve the integration of third-party and internal APIs used across the pipeline. This includes:

- Unifying the way metadata and embeddings are extracted.
- Adding error handling and fallback mechanisms.
- Streamlining authentication and response validation.

---

## 2. More Robust Scraping

Enhance scraping capabilities to include:

- Full HTML content ingestion and parsing.
- Flexible filtering based on tags, structure, or page regions.
- Better noise reduction from non-document content.

---

## 3. Pipeline Cohesion

Work toward bringing all modular components into a coherent pipeline:

- Design a central orchestrator or runner script.
- Establish shared configurations and logging conventions.
- Ensure smooth handoff between scraping, parsing, scoring, and storage.

---

## 4. CI with GitHub Actions

Lay the foundation for automation and reproducibility:

- Set up GitHub Actions for linting, testing, and basic pipeline validation.
- Include periodic test runs and scheduled checks.
- Add coverage for core modules and data integrity checks.

---