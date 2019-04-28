
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

.PHONY: sdist
sdist:
	python setup.py sdist

.PHONY: wheel
wheel:
	python setup.py bdist_wheel

.PHONY: release
release: clean sdist wheel
	twine --version
	twine upload -s dist/*

.PHONY: check-docs
check-docs:
	echo TODO

.PHONY: deb-stretch-local
deb-stretch-local: clean sdist
	docker build -t afancontrol-debuild -f ./Dockerfile.debian .
	docker run -it --rm \
		-v `pwd`/dist:/afancontrol/dist \
		afancontrol-debuild sh -ex -c '\
			tar xaf /afancontrol/dist/afancontrol-*.tar.gz --strip 1; \
			debuild -us -uc -b; \
			cd ../; \
			ls -alh; \
			mkdir /afancontrol/dist/debian; \
			cp afancontrol?* /afancontrol/dist/debian/; \
	'

.PHONY: deb-stretch-from-pypi
deb-stretch-from-pypi: clean
	docker build -t afancontrol-debuild -f ./Dockerfile.debian .
	docker run -it --rm \
		-v `pwd`/dist:/afancontrol/dist \
		afancontrol-debuild sh -ex -c '\
			uscan --download --overwrite-download --verbose; \
			tar xaf ../afancontrol_*.orig.tar.gz --strip 1; \
			debuild -us -uc; \
			cd ../; \
			ls -alh; \
			mkdir /afancontrol/dist/debian; \
			cp afancontrol?* /afancontrol/dist/debian/; \
	'
