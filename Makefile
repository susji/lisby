# In case your default Python 3 interpreter is older than 3.6,
# please set PYTHON=/path/to/newer. The lisby code makes heavy
# use of type hints, and those were introduced in 3.6.
TESTFLAGS :=
LINTFLAGS := -E
MYPYFLAGS :=
PYTHON := python3
VENV := venv

note:
	@echo To automatically set up the suitable virtualenv, and run the
	@echo associated tests, run
	@echo
	@echo "    $$ make all"
	@echo
	@echo lisby requires Python 3.6 or newer. For an alternative Python
	@echo interpreter, run make with \`PYTHON=/path/to/python\`.
	@echo
	@echo To run lisby REPL directly from the virtualenv, run
	@echo
	@echo "    $$ make run"
	@echo
	@echo If your virtualenv is non-functional, run \`make clean\` first.
	@echo

run: $(VENV)
	$(VENV)/bin/python3 -m lisby

all: test mypy lint

test: $(VENV)
	$(VENV)/bin/python3 -m unittest $(TESTFLAGS)

mypy: $(VENV)
	$(VENV)/bin/mypy $(MYPYFLAGS) lisby

lint: $(VENV)
	$(VENV)/bin/pylint $(LINTFLAGS) lisby

$(VENV):
	$(PYTHON) -m venv $(VENV)
	$(VENV)/bin/pip3 install -r requirements.txt
	$(VENV)/bin/pip3 install -e .

.PHONY: note all test lint mypy run
