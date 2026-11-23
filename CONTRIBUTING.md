# Contributing to afancontrol

I started afancontrol in 2013 in an attempt to make my custom PC case quiet.
It's been working 24/7 ever since with no issues, and eventually I started using
it on my other machines as well.

I'm quite happy with how this package serves my needs, and I hope
it can be useful for someone else too.

Contributions are welcome. Please keep the following in mind.

* Complex features and large diffs would probably be rejected
  because they would make maintenance more complicated for me.
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

After writing a small piece of code and its tests, I run these three
commands and fix any errors until the commands pass.

To build docs:

    make docs
