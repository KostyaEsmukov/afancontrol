
.PHONY: format
format:
	black src tests *.py && isort src tests *.py

.PHONY: lint
lint:
	flake8 src tests *.py && isort --check-only src tests *.py && black --check src tests *.py && mypy src tests

.PHONY: test
test:
	coverage run -m py.test
	coverage report

.PHONY: clean
clean:
	find . -name "*.pyc" -print0 | xargs -0 rm -f
	rm -Rf dist
	rm -Rf *.egg-info

.PHONY: develop
develop:
	pip install -U setuptools wheel
	pip install -e '.[arduino,metrics,dev]'

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

.PHONY: docs
docs:
	make -C docs html

.PHONY: check-docs
check-docs:
	# Doesn't generate any output but prints out errors and warnings.
	make -C docs dummy

.PHONY: deb-local
deb-local: clean sdist
	docker build -t afancontrol-debuild -f ./Dockerfile.debian .
	docker run -it --rm \
		-e DEBFULLNAME="`git config --global user.name`" \
		-e DEBEMAIL="`git config --global user.email`" \
		-v `pwd`/dist:/afancontrol/dist \
		-v `pwd`/debian:/afancontrol/debian \
		afancontrol-debuild sh -ex -c '\
			tar xaf /afancontrol/dist/afancontrol-*.tar.gz --strip 1; \
			dch -v `python3 setup.py --version` -b --distribution=unstable; \
			debuild -us -uc -b; \
			cp debian/changelog /afancontrol/debian/; \
			cd ../; \
			ls -alh; \
			mkdir /afancontrol/dist/debian; \
			cp afancontrol?* /afancontrol/dist/debian/; \
			dpkg --contents afancontrol*.deb; \
	'

.PHONY: deb-from-pypi
deb-from-pypi: clean
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
