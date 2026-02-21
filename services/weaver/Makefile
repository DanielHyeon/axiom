.PHONY: unit integration-external-exit-gate

unit:
	PYTHONPATH=. pytest -q tests/unit

integration-external-exit-gate:
	PYTHONPATH=. python3 scripts/weaver_external_exit_gate.py --loops $${LOOPS:-2}
