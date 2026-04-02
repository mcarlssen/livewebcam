.PHONY: install-editable install-pipx help

help:
	@echo "Targets:"
	@echo "  install-pipx     pipx install .   (recommended for end users)"
	@echo "  install-editable pip install -e . (developers, current venv)"

install-pipx:
	pipx install .

install-editable:
	pip install -e .
