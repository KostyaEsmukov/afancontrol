
.PHONY: format
format:
	black src tests *.py && isort -rc src tests *.py

.PHONY: lint
lint:
	flake8 src tests *.py && isort --check-only -rc src tests *.py && black --check src tests *.py && mypy src tests

.PHONY: test
test:
	coverage run -m py.test
	coverage report

.PHONY: clean
clean:
	find . -name "*.pyc" -print0 | xargs -0 rm -f
	rm -Rf dist
	rm -Rf *.egg-info

.PHONY: wheel
wheel: clean
	python setup.py bdist_wheel
