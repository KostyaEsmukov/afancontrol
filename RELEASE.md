# Release process

## Release

1. Bump version in `src/afancontrol/__init__.py`
1. Generate debian/changelog record with `dch`
1. `make release`
1. `git tag -s 3.0.0` + `git push origin 3.0.0`
1. Create a new release for the pushed tag at https://github.com/KostyaEsmukov/afancontrol/releases
1. Upload a GPG signature of the tarball to the just created GitHub release,
   see https://wiki.debian.org/Creating%20signed%20GitHub%20releases

## Check

1. `make deb-from-github`
1. `docker run -it --rm python:3.7 bash` + `pip install afancontrol` + `afancontrol --help`
1. Ensure that the CI build for the tag is green.
