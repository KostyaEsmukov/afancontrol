# Contributing to afancontrol

I started afancontrol in 2013 in an attempt to make my custom PC case quiet.
It's been working 24/7 ever since with no issues, and eventually I started using
it on my other machines as well.

I'm quite happy with how this package serves my needs, and I hope
it can be useful for someone else too.

Contributions are welcome, however, keep in mind, that:
* Complex features and large diffs would probably be rejected,
  because it would make maintenance more complicated for me,
* I don't have any plans for active development and promotion
  of the package.


## Dev workflow

Prepare a virtualenv:

    mkvirtualenv afancontrol
    make develop

I use [TDD](https://en.wikipedia.org/wiki/Test-driven_development) for development.

Run tests:

    make test

Autoformat the code and imports:

    make format

Run linters:

    make lint

So essentially after writing a small part of code and tests I call these
three commands and fix the errors until they stop failing.

To build docs:

    make docs
