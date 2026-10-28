# Slide spec format

`scripts/build_slides.py` renders a JSON file in this format. The title slide is
generated automatically from the top-level fields. Every text field accepts
inline `**bold**`, `*italic*` and `` `code` ``.

```json
{
  "title": "Introduction to Neural Networks",
  "subtitle": "Lecture 4",
  "course": "ETM 572 · AI Fundamentals",
  "author": "Instructor name",
  "date": "Fall 2026",
  "answer_key": true,
  "slides": [ ... ]
}
```

| Field | Required | Notes |
|---|---|---|
| `title` | yes | Lecture title, shown on the title slide and in PDF metadata |
| `subtitle` | no | Lecture number or a one-line description |
| `course` | no | Shown on the title slide and in every footer. Falls back to `title` |
| `author`, `date` | no | Only include if they appear in the notes or the user gave them |
| `answer_key` | no | Default `true`. Set `false` to omit answers from the deck |

## Slide types

### `section`: divider between major topics
```json
{"type": "section", "title": "Part 2: Training", "subtitle": "How networks learn"}
```

### `bullets`: the main content slide
```json
{
  "type": "bullets",
  "title": "What a neuron computes",
  "bullets": [
    "Takes a **weighted sum** of its inputs plus a bias",
    {"text": "Passes the sum through an activation function", "sub": ["ReLU: max(0, x)", "Sigmoid: squashes to 0..1"]},
    "Output becomes input to the next layer"
  ],
  "note": "Optional callout box: an example, analogy or common mistake."
}
```
A bullet is either a string or `{"text": ..., "sub": [strings]}`. `note` is optional.

### `two_column`: comparisons, pros and cons, before and after
```json
{
  "type": "two_column",
  "title": "Supervised vs unsupervised",
  "left":  {"heading": "Supervised",   "bullets": ["Labeled data", "Predicts a target"]},
  "right": {"heading": "Unsupervised", "bullets": ["No labels", "Finds structure"]}
}
```

### `definition`: one important term in focus
```json
{"type": "definition", "title": "Key concept", "term": "Overfitting",
 "definition": "When a model learns noise in the training data and performs worse on new data.",
 "example": "A model that memorizes practice exam answers but fails the real exam."}
```

### `code`: code, formulas or pseudo-code, rendered in monospace
```json
{"type": "code", "title": "Gradient descent update", "code": "w = w - lr * grad\nb = b - lr * grad_b", "caption": "Repeat until loss stops improving"}
```

### `takeaways`: summary slide with check marks
```json
{"type": "takeaways", "title": "Key Takeaways", "bullets": ["...", "..."]}
```

### `questions`: review questions, paginated automatically
```json
{"type": "questions", "title": "Review Questions", "questions": [
  {"q": "What does the activation function add to a neuron?", "answer": "Non-linearity, so the network can model curved relationships."}
]}
```
Answers are collected onto **Answer Key** slides at the very end of the deck.

### `glossary`: term and definition table, paginated automatically
```json
{"type": "glossary", "title": "Glossary", "terms": [
  {"term": "Epoch", "definition": "One full pass through the training data."}
]}
```

## Layout limits

- Font sizes shrink automatically from 24pt to 15pt to fit. Below that the script
  reports `OVERFLOW` and exits with code 2. Split the slide and rebuild.
- Titles must fit in two lines at 24pt (about 90 characters at most, aim for under 60).
- Code blocks fit about 18 lines and 80 characters per line.
- Glossary, questions and answer key slides add continuation pages on their own.
