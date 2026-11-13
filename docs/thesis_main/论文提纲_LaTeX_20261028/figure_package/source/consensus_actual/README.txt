Formal Figure 6: real observations -> saved coordinate medians -> six-corner layout.
Run: python figure_package/source/consensus_actual/build_fig06.py
Outputs replace figure_package/panels/fig06/a_upper_evidence, b_lower_evidence, c_actual_layout, legend as PDF/SVG/600 dpi PNG.
The original 1024 x 512 panorama registration, contributor records and saved output are preserved in data/.
verify() checks unique-person votes, membership, coordinate medians, exact selected-node membership in the final output, floor reconstruction and round-trip panorama projection. No team experiment or clustering is rerun.
The supplied LaTeX already fixes each panel at 0.322 x 170 mm = 54.74 mm. This script draws at that physical size; captions remain in LaTeX.
Source recovered from the previously delivered complete v2 package; data are byte-identical to the current dot_fig07 source.
