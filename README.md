# AI Lecture Skipper

An open-source, AI-powered tool that analyzes YouTube lectures and identifies which sections are worth watching, skimming, or skipping.

AI Lecture Skipper uses locally hosted large language models (LLMs) through **Ollama** to analyze lecture transcripts and generate timestamped recommendations, helping students spend less time watching repetitive or irrelevant content.

**No paid AI API keys required.**

## Features

- **YouTube Integration:** Analyze lectures directly from a YouTube URL without manually uploading videos.
- **Automatic Transcript Extraction:** Retrieve timestamped transcripts from YouTube captions.
- **Local AI Processing:** Use Ollama to run open-weight language models locally without per-request API fees.
- **Smart Recommendations:** Classify lecture segments as `WATCH`, `SKIM`, or `SKIP`.
- **Topic Identification:** Break lectures into meaningful sections based on their content.
- **Timestamped Navigation:** Generate links that jump directly to specific sections of a YouTube video.
- **Explainable Recommendations:** Provide reasoning behind each classification.

## How It Works

```text
YouTube URL
    |
    v
Transcript Extraction
    |
    v
Transcript Segmentation
    |
    v
Local LLM (Ollama)
    |
    v
Content Classification
    |
    v
Timestamped Recommendations
    |
    v
WATCH / SKIM / SKIP
```

1. **Input:** The user provides a YouTube lecture URL.
2. **Extraction:** The application retrieves the video's transcript with timestamps.
3. **Segmentation:** The transcript is divided into manageable sections.
4. **Analysis:** A locally hosted LLM evaluates each section's educational importance.
5. **Classification:** Sections are labeled `WATCH`, `SKIM`, or `SKIP`.
6. **Output:** The application generates a timestamped watchlist containing explanations and YouTube links.

## Tech Stack

| Technology | Purpose |
|---|---|
| Python | Core application and backend processing |
| Ollama | Local LLM inference |
| Qwen3 4B Instruct | Default AI model |
| youtube-transcript-api | YouTube transcript extraction |
| Pydantic | Structured output schemas and validation |
| pytest | Tests with mocked external services |
| FastAPI (planned) | Backend REST API |
| React + TypeScript (planned) | Interactive user interface |

## Getting Started

### Prerequisites

- Python 3.10 or newer (the installed environment uses Python 3.10)
- Ollama installed locally
- Sufficient system memory to run a local LLM
- A YouTube video with accessible captions

### 1. Clone the Repository

```bash
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git
cd YOUR_REPO
```

### 2. Create a Virtual Environment

```bash
python -m venv .venv
```

Activate the environment.

**Windows:**

```powershell
.\.venv\Scripts\Activate.ps1
```

**macOS/Linux:**

```bash
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
python -m pip install -r requirements.txt

# Optional: install the lecture-skipper command for editable development
python -m pip install -e .
```

If PowerShell blocks activation, use the environment's interpreter directly:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 4. Install Ollama

Download Ollama from:

https://ollama.com/download

Once installed, download the recommended model:

```bash
ollama pull qwen3:4b-instruct-2507-q4_K_M
```

Verify that the model is available:

```bash
ollama list
```

Test the model:

```bash
ollama run qwen3:4b-instruct-2507-q4_K_M
```

Ollama exposes a local API at `http://localhost:11434`.

The application communicates with this API to analyze lecture transcripts.

The CLI defaults to your installed local model name `qwen3:4b-instruct`. If `ollama list` already shows it, no download is needed. If starting from scratch, use the published tag above and pass `--model qwen3:4b-instruct-2507-q4_K_M`, or create the matching local alias:

```powershell
ollama cp qwen3:4b-instruct-2507-q4_K_M qwen3:4b-instruct
```

If Ollama is not running, open the Ollama application or run `ollama serve`. Inference always connects to `http://localhost:11434`, ignoring remote host and proxy settings. Cloud models are rejected; choose a downloaded local model.

### 5. Run the Application

Run the command-line application:

```bash
python main.py
```

Enter a YouTube lecture URL when prompted.

You can also supply a URL directly and save the JSON result:

```bash
python main.py "https://www.youtube.com/watch?v=VIDEO_ID" --output output/analysis.json
```

By default, the CLI analyzes only captions starting in the first **15 minutes** and saves `outputs/VIDEO_ID.json` and `outputs/VIDEO_ID.md`. A caption crossing the time limit is kept whole, so the final timestamp can extend slightly beyond it. The terminal shows a readable chronological summary; Markdown includes clickable timestamp links. Re-running the same video overwrites its reports unless you choose another output path.

```powershell
# Run without activating the virtual environment
.\.venv\Scripts\python.exe main.py "https://www.youtube.com/watch?v=VIDEO_ID"

# Full lecture
.\.venv\Scripts\python.exe main.py "https://youtu.be/VIDEO_ID" --full

# Short CPU test with smaller sections
.\.venv\Scripts\python.exe main.py "https://youtu.be/VIDEO_ID" --max-minutes 2 --chunk-seconds 120

# Published model tag instead of the local alias
.\.venv\Scripts\python.exe main.py "https://youtu.be/VIDEO_ID" --model qwen3:4b-instruct-2507-q4_K_M

# Machine-readable stdout and a custom report folder
.\.venv\Scripts\python.exe main.py "https://youtu.be/VIDEO_ID" --json --output-dir outputs/my-course
```

Replace `VIDEO_ID` with a real 11-character YouTube video ID, or paste the complete video URL. Running `python main.py` without a URL prompts for one.

| Option | Purpose | Default |
|---|---|---|
| `--model` | Installed local Ollama model | `qwen3:4b-instruct` |
| `--chunk-seconds` | Target section duration | 300 |
| `--max-minutes` | Analyze captions starting before this minute | 15 |
| `--full` | Analyze the full lecture; excludes `--max-minutes` | Off |
| `--languages` | Caption language preference, e.g. `en es` | `en` |
| `--timeout-seconds` | Timeout per local Ollama request | 600 |
| `--output-dir` | Folder for JSON and Markdown reports | `outputs` |
| `--output` | Custom `.json` path; `.md` is saved beside it | Not set |
| `--json` | JSON on stdout instead of the readable summary | Off |

Sections retain exact source caption records and timestamps. They target five minutes but split earlier when needed to stay within **3000 UTF-8 bytes** of transcript text. Inference uses a **4096-token context**, generates up to 384 tokens per response, disables model thinking, and runs sequentially to suit CPU inference on a Ryzen 5 5600U with 16 GB RAM. Progress goes to stderr. Low-confidence `SKIP` decisions become `SKIM`. These initial sections use duration and text limits rather than semantic topic boundaries.

### Development and Build

```bash
python -m pip install -r requirements-dev.txt
python -m pip install -e .
python -m pytest -q
python -m pip check
python -m build
```

Build artifacts, virtual environments, caches, and generated report directories are ignored by Git. Tests mock YouTube and Ollama calls and do not require network access or a running model. Builds produce a wheel and source archive in `dist/`. With setuptools>=68 and wheel installed, `python -m build --no-isolation` also works without downloading an isolated build environment. Coding agent instructions are in [agents/agents.md](agents/agents.md), linked from the root [AGENTS.md](AGENTS.md).

The modular Python package is `ai_lecture_skipper/`: `youtube.py`, `segmentation.py`, `analyzer.py`, `models.py`, `pipeline.py`, and `output.py`. `main.py` provides the CLI; `lecture_skipper.py` preserves the original helper API. The future React interface is outside this MVP.

## Example Output

**Input:**

```text
https://www.youtube.com/watch?v=VIDEO_ID
```

**Output:**

| Timestamp | Topic | Recommendation |
|---|---|---|
| 00:00–05:30 | Course announcements | SKIP |
| 05:30–14:20 | Review of previous lecture | SKIM |
| 14:20–28:45 | Introduction to recurrence relations | WATCH |
| 28:45–42:10 | Additional practice examples | SKIM |
| 42:10–58:30 | Master theorem | WATCH |

*This is illustrative full-lecture output rather than an analysis of an actual lecture. Use `--full` to analyze beyond the default 15-minute window.*

### Example JSON Response

```json
{
  "video_id": "VIDEO_ID",
  "model": "qwen3:4b-instruct",
  "max_minutes": 15,
  "truncated": true,
  "warnings": ["Transcript-only analysis can miss equations, slides, and other visual content. Check the video before skipping important material."],
  "segments": [
    {
      "start": 600,
      "end": 900,
      "topic": "Introduction to recurrence relations",
      "recommendation": "WATCH",
      "reason": "Introduces a new mathematical technique.",
      "confidence": 0.94,
      "youtube_url": "https://www.youtube.com/watch?v=VIDEO_ID&t=600s"
    }
  ]
}
```

## Recommendation Criteria

### WATCH

Content that is important for understanding the lecture.

- New concepts and definitions
- Algorithms and mathematical proofs
- Important worked examples
- Exam-relevant explanations
- Complex or unfamiliar material

### SKIM

Content that provides useful reinforcement but may not require full attention.

- Reviews of previous material
- Repetitive explanations
- Additional examples of familiar concepts
- Extended elaborations of already-covered topics

### SKIP

Content that contributes little new educational information.

- Nonessential announcements
- Long pauses or technical interruptions
- Repeated explanations without new information
- Off-topic discussions

The system prioritizes avoiding false `SKIP` recommendations. Ambiguous or uncertain sections should default to `SKIM` or `WATCH`.

## Local Model Configuration

The default model is **Qwen3 4B Instruct**.

Other Ollama-compatible models can be used depending on available hardware.

| Model | Approx. Download Size | Intended Use |
|---|---|---|
| Qwen3 1.7B | 1.4 GB | Lower-memory devices |
| Qwen3 4B Instruct | 2.5 GB | Default lecture analysis |
| Qwen3 8B | 5.2 GB | More capable local analysis |

Model choice affects inference speed, memory consumption, and recommendation quality.

## Roadmap

### Phase 1 — Core MVP

- [x] YouTube URL parsing and validation
- [x] Timestamped transcript extraction
- [x] Local Ollama integration
- [x] Transcript chunking and segmentation
- [x] AI-generated WATCH / SKIM / SKIP classifications
- [x] Structured JSON output
- [x] Clickable YouTube timestamps

### Phase 2 — Web Application

- [ ] FastAPI backend
- [ ] React + TypeScript frontend
- [ ] YouTube video player integration
- [ ] Color-coded lecture timeline
- [ ] Interactive segment navigation
- [ ] Configurable local model selection

### Phase 3 — Personalized Learning

- [ ] Upload syllabi, lecture notes, and course materials
- [ ] Identify concepts previously covered in lectures
- [ ] Track familiar and unfamiliar topics
- [ ] Generate personalized skip recommendations
- [ ] Compare lecture content against learning objectives
- [ ] Generate summaries of skipped sections

### Phase 4 — Advanced Analysis

- [ ] Extract video frames for slide and whiteboard analysis
- [ ] Detect important formulas and visual demonstrations
- [ ] Improve topic boundary detection
- [ ] Automatically revisit low-confidence classifications
- [ ] Evaluate recommendation accuracy against manually labeled lectures

## Limitations

- Transcript extraction requires accessible YouTube captions.
- YouTube may restrict automated transcript retrieval.
- Automatically generated captions may contain inaccuracies.
- Transcript-only analysis cannot reliably interpret visual information such as handwritten equations, slides, and diagrams.
- Smaller local models may produce inconsistent recommendations.
- Lecture importance is subjective and depends on the student's existing knowledge.
- Local inference performance depends on available CPU, GPU, and memory resources.
- Each section is analyzed independently; familiarity with earlier lectures is not inferred.
- The first 15 minutes are analyzed by default. Use `--full` to include later material.
- An unusually large individual caption is rejected with an explicit error rather than silently truncated.
- Confidence values are model estimates, not calibrated probabilities.

### Troubleshooting

| Error | What to do |
|---|---|
| Cannot connect to Ollama | Open Ollama or run `ollama serve`; verify localhost port 11434. |
| Model is not installed | Run `ollama list`; select an installed model with `--model`, or pull the published tag above. |
| No captions available | Check the video's CC menu; choose a captioned video or another `--languages` value. |
| YouTube blocked transcript retrieval | Try later or another network. The application does not download videos or bypass restrictions. |
| Invalid structured output | Retry with `--chunk-seconds 120` or another instruction model. Invalid classifications are never returned as successful results. |
| CPU inference timeout | Increase `--timeout-seconds`, shorten chunks, close memory-heavy programs, or use a smaller installed model. |
| Cannot save reports | Choose a writable `--output-dir`. |

## Privacy and Cost

AI Lecture Skipper is designed to run inference locally.

- No paid LLM API subscription is required.
- Lecture transcripts are processed by a locally hosted model.
- No transcript data needs to be sent to a third-party AI inference provider.
- Internet access is still required to retrieve YouTube transcripts and download models.
- Hardware, electricity, and internet costs may still apply.

## Project Status

**Early Development — MVP**

The command-line MVP accepts a YouTube URL, retrieves a timestamped transcript, analyzes bounded sections using Ollama, and produces timestamped recommendations in readable, JSON, and Markdown formats. Automated tests mock transcript retrieval and inference; live use requires accessible captions and a running Ollama server with the selected model installed.

Future versions will introduce a web interface, personalized recommendations, and visual lecture analysis.

## License

MIT. See [LICENSE](LICENSE).
