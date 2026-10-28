---
name: lecture_slides
description: Convert a PDF of lecture notes into a dark-theme 16:9 slide deck PDF that can be shared with students as a study handout, ending with key takeaways, review questions with an answer key and a glossary. Use when the user provides lecture notes, class notes or a course reading as a PDF and wants slides, a deck or a handout made from them.
---

# Lecture notes to student slides

Turn a lecture-notes PDF into a slide deck PDF students can study from on their
own. The deck is a **study handout**: each slide carries enough detail to make
sense without the lecturer, but stays scannable.

Everything is relative to this skill's folder. Scripts live in `scripts/`, the
JSON format is documented in `reference/slide_spec.md`.

## Inputs

- A PDF of lecture notes. If the user did not say where it is, look in `input/`
  first, then the working directory.
- Optional instructions from the user (audience level, focus topics, slide count,
  course name, things to leave out). User instructions override the defaults below.

## Output

- One PDF saved to `output/<input-name>-slides.pdf` unless the user names another
  path. Create the folder if needed.
- Keep intermediate files (`notes.txt`, `slides.json`) in `work/`.

## Workflow

### 1. Read the notes
```bash
python <skill-dir>/scripts/extract_notes.py input/<file>.pdf work/notes.txt
```
Read `work/notes.txt` in full. If the script warns about pages with little text,
open those pages with the Read tool to see diagrams, tables, handwriting or
scanned content. Do not skip them; diagrams often carry key ideas.

### 2. Plan the deck
Before writing JSON, outline it:
- Identify the lecture title, course name and the 3 to 6 major topics.
- Follow the order of the notes unless reordering clearly helps understanding.
- Size the deck to the material: roughly one content slide per main idea. As a
  guide, 10 to 25 content slides for a typical lecture. Don't pad thin notes and
  don't cram dense ones.

### 3. Write `work/slides.json`
Read `reference/slide_spec.md` for the exact format. Structure the deck as:

1. Title slide (automatic from top-level fields)
2. For each major topic: a `section` slide, then its content slides
3. `takeaways`: 4 to 7 of the most important ideas from the whole lecture
4. `questions`: 5 to 10 review questions with answers
5. `glossary`: every technical term a student needs, alphabetical
6. Answer key (automatic from question answers)

Writing rules for study-handout density:
- **3 to 6 bullets per slide**, each a complete thought a student can understand
  when reviewing alone. Prefer short sentences over fragments like "Gradients".
- Use sub-bullets for examples, formulas or details that belong to one point.
- Use the `note` callout for an example, analogy or common misconception, at most
  one per slide.
- Slide titles state the idea, not just the topic: "Learning rate controls step
  size" is better than "Learning rate".
- Use `two_column` for comparisons, `definition` for the 2 to 4 most central
  concepts, `code` for code, formulas or algorithms.
- Bold only the key term in a bullet, never whole sentences.
- **Stay faithful to the notes.** Rephrase and condense, but don't add facts,
  numbers, dates or claims that are not in the notes. If the notes contain an
  apparent error, keep their content and mention the issue to the user at the end
  rather than silently correcting it.
- Do not include `author` or `date` unless they appear in the notes or the user
  provided them.

Review questions:
- Mix recall ("What is...") with understanding ("Why does...", "What would happen
  if...") and at least one application question.
- Every answer must be supported by the notes. Keep answers to 1 to 3 sentences.

Glossary:
- Plain-language definitions of one or two sentences, consistent with the notes.

### 4. Build the PDF
```bash
python <skill-dir>/scripts/build_slides.py work/slides.json output/<name>-slides.pdf
```
If it exits with `OVERFLOW / LAYOUT PROBLEMS`, fix each listed slide (split a
crowded slide into two, shorten a long title or trim a code block) and rebuild.
Repeat until it exits cleanly.

The script needs `reportlab`. If it is missing, install it with
`pip install reportlab pdfplumber`.

### 5. Check the result
- Confirm the page count is reasonable and the file opens.
- If you can view images, render two or three pages and look at them, for example
  `pdftoppm -png -r 50 -f 2 -l 4 output/<name>-slides.pdf work/preview`, then
  open the PNGs with the Read tool. Check for text running off slides or crowding.
- Spot-check that the review answers and glossary definitions match the notes.

### 6. Report back
Tell the user briefly: where the PDF is, how many slides, the topics covered and
anything you could not convert well (unreadable pages, diagrams you could only
describe, apparent errors in the notes).

## Limitations

- Diagrams and images from the notes are not copied onto slides. Describe the key
  idea from a diagram in bullets instead, and mention this to the user.
- Math is rendered as plain text. Use Unicode symbols (², √, ≤, Σ, θ) and the
  `code` slide for multi-line formulas.
