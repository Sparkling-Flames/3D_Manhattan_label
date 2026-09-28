# English elsarticle manuscript

This ignored, English-only workspace contains two PDFLaTeX entry points:

- `main.tex`: the eight-section research article.
- `supplement.tex`: a lean, standalone supplement.

Active article sections are `sections/01_introduction.tex` through
`sections/08_conclusion.tex`. The former `06_future_work.tex` and
`07_appendix.tex` are retained as legacy drafts but are not compiled.

The bibliography is `refs/references.bib`, using the bundled
`elsarticle-num.bst` style. Compile each entry point with PDFLaTeX, BibTeX,
and two further PDFLaTeX passes.

Draft markers are part of the evidence contract:

- `[EXPECTED_RESULT_NOT_OBSERVED]` marks planned result prose that is not evidence.
- `TBD_DATA` marks every unavailable numerical result.
- `[ETHICS_STATUS_TO_VERIFY]` marks the unresolved approval-or-exemption statement.

No manuscript containing any of these markers is submission-ready. The
machine-readable method contract and repository audit artefacts remain the
normative sources; they are referenced rather than copied into this project.
