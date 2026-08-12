PYTHON ?= .venv/bin/python
MODE ?= open
FOCUS ?=
MAX_CANDIDATES ?= 5
MARKET ?= KR
LANGUAGE ?= ko
CANDIDATE_COUNT ?= 5
INPUT ?= verified-urls.json

.PHONY: discover discover-daily discover-from-urls gui gui-build test lint typecheck

discover:
	$(PYTHON) -m src.cli discover --mode "$(MODE)" --max-candidates "$(MAX_CANDIDATES)" $(if $(FOCUS),--focus "$(FOCUS)",)

discover-daily:
	$(PYTHON) -m src.cli discover-daily --mode "$(MODE)" --market "$(MARKET)" --language "$(LANGUAGE)" --candidate-count "$(CANDIDATE_COUNT)" $(if $(FOCUS),--focus "$(FOCUS)",)

discover-from-urls:
	$(PYTHON) -m src.cli discover-from-urls --input "$(INPUT)"

gui:
	LLM_PROVIDER=$${LLM_PROVIDER:-codex} $(PYTHON) -m src.desktop

gui-build:
	$(PYTHON) -m PyInstaller --noconfirm --clean packaging/idea-graph-gui.spec

test:
	$(PYTHON) -m pytest

lint:
	$(PYTHON) -m ruff check .

typecheck:
	$(PYTHON) -m mypy src
