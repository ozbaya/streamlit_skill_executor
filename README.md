# Streamlit Skill Executor

This folder holds two things:

1. **A Claude Code skill, `lecture_slides`**, that turns a PDF of lecture notes into a
   dark-theme 16:9 slide deck PDF for students. The deck ends with key takeaways,
   review questions with an answer key, and a glossary.
2. **A Streamlit app (`app.py`)** that runs that skill, or any other skill folder
   with a `SKILL.md`, from a web page. You upload a PDF, add optional instructions,
   and download the PDF the skill produces. You don't have to open Claude Code.

## Folder layout

```
.
├── .claude/skills/lecture_slides/   # The skill
│   ├── SKILL.md                     # Instructions Claude follows
│   ├── scripts/extract_notes.py     # PDF -> text (pdfplumber / pypdf)
│   ├── scripts/build_slides.py      # slides.json -> slide PDF (reportlab)
│   └── reference/slide_spec.md      # JSON format for slides.json
├── app.py                           # Streamlit front end (Claude Agent SDK)
├── requirements.txt                 # Python dependencies
├── source_pdfs/                     # Sample input PDFs
├── work/                            # Intermediate files from Claude Code runs
├── output/                          # Slide decks from Claude Code runs
├── runs/                            # One folder per Streamlit run (created by the app)
└── .env                             # Auth token (not committed)
```

## Two ways to run the skill

### Option A: In Claude Code

Open Claude Code in this folder. It picks up the skill from `.claude/skills/`.
Then ask for it:

```
/lecture_slides Make slides from source_pdfs/Advanced RAG.pdf
```

You can also just describe what you want ("turn these lecture notes into slides").
Claude saves intermediate files in `work/` and the finished deck in
`output/<name>-slides.pdf`.

### Option B: In the Streamlit app

The app uses the [Claude Agent SDK](https://docs.claude.com/en/api/agent-sdk/overview)
to run the same skill without the Claude Code interface. On each run it:

1. Creates a new folder under `runs/<timestamp>/`.
2. Copies the chosen skill into `runs/<timestamp>/.claude/skills/<skill-name>/`
   and saves the uploaded PDF to `input/`.
3. Starts an agent in that folder with the prompt `/<skill-name> ...` plus your
   instructions, and streams its messages and tool calls to the page.
4. Blocks some shell commands (`sudo`, `curl`, `wget`, `rm -rf /`, and others) with
   a pre-tool hook.
5. Collects the PDFs written to `output/`, shows download buttons, and reports the
   run's cost.

## Setup

You need Python 3.10 or newer.

### 1. Create and activate a virtual environment

From this folder:

```bash
cd /path/to/streamlit_skill_executor
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
```

Your prompt should now start with `(.venv)`. Run `deactivate` when you're done.

### 2. Install dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

This installs Streamlit, the Claude Agent SDK, `python-dotenv`, and the libraries the skill's
scripts use (`pypdf`, `pdfplumber`, `reportlab`).

Optional: the skill can render preview images of the slides with `pdftoppm`
to check the layout. On macOS, install it with `brew install poppler`.

### 3. Set up authentication

The Agent SDK needs one of these environment variables:

- `ANTHROPIC_API_KEY`: an API key from the [Claude Console](https://console.anthropic.com/).
  Usage is billed to that account.
- `CLAUDE_CODE_OAUTH_TOKEN`: a token for your Claude subscription. Create one with
  `claude setup-token`.

Put it in `.env`:

```
CLAUDE_CODE_OAUTH_TOKEN=your-token-here
```

`app.py` loads `.env` automatically at startup with `python-dotenv`. `find_dotenv()`
looks for the file in the app's folder first, then in each parent folder. A variable
that's already set in your shell takes precedence over the value in `.env`.

`.env` is listed in `.gitignore`. Don't commit it.

### 4. Run the Streamlit app

```bash
streamlit run app.py
```

Streamlit opens the app in your browser, at http://localhost:8501 by default.

### 5. Use the app

1. In the sidebar, set **Skill folder path** to the folder that contains `SKILL.md`,
   for example:
   ```
   /path/to/streamlit_skill_executor/.claude/skills/lecture_slides
   ```
2. Upload a lecture-notes PDF. To test, use `source_pdfs/Advanced RAG.pdf`.
3. Optionally add instructions, such as the audience level, slide count, course
   name, or topics to focus on.
4. Click **Run** and watch the progress log.
5. When the run finishes, click **Download** to get the slide deck. All files from
   the run stay in `runs/<timestamp>/`.

### Quick start

After the first setup, these commands start the app:

```bash
cd /path/to/streamlit_skill_executor
source .venv/bin/activate
streamlit run app.py
```

## Notes

- A run can take several minutes and uses up to 40 agent turns. The cost appears
  after each run.
- Diagrams and images in the notes aren't copied onto the slides. The skill
  describes them in bullet points instead.
- `runs/` grows with every run. Delete old run folders when you no longer need them,
  and consider adding `runs/` to `.gitignore`.
