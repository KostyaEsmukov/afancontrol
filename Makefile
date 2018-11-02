
.PHONY: format
format:
	black afancontrol tests *.py && isort -rc afancontrol tests *.py

.PHONY: lint
lint:
	flake8 afancontrol tests *.py && isort --check-only -rc afancontrol tests *.py && black --check afancontrol tests *.py && mypy afancontrol tests

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
