
# Ribosome example: Nginx configuration files

This repo is example of configured [Ribosome](https://github.com/alexandervpetrov/ribosome)
release process for Nginx configuration files.
This example is complementary to [Django example](https://github.com/alexandervpetrov/ribosome-example-django),
they work together.


## Prerequisites

Install [pyenv](https://github.com/pyenv/pyenv):
packages needed to build Python by [this guide](https://askubuntu.com/a/865644)
and then use [pyenv-installer](https://github.com/pyenv/pyenv-installer#installation--update--uninstallation).

Ensure that pyenv shims come first at PATH.
Place these lines

    export PATH="~/.pyenv/bin:$PATH"
    eval "$(pyenv init -)"
    eval "$(pyenv virtualenv-init -)"

as last ones in `.bashrc` for interactive sessions **and**
also in `.bash_profile` for non-interactive sessions.

Install Python 3.6.5: `pyenv install 3.6.5`.

Install [Pipenv](https://github.com/pypa/pipenv)
into 3.6.5 distribution: `pip install pipenv`.

Install Nginx.


## Getting started

Setup runtime and build environment:

    $ make devsetup

E.g. install configuration `dev` from service `nginxmain`:

    $ sudo $(pipenv --py) ./service.py install nginxmain dev

E.g. install configuration `dev` from service `nginxsite`:

    $ sudo $(pipenv --py) ./service.py install nginxsite dev


## Releasing, deploying, running

Set the S3 bucket name in `codons.yaml` to the one you own.
Ensure you [configured](https://boto3.readthedocs.io/en/latest/guide/quickstart.html#configuration) S3 access.
Setup SSH daemon at localhost to test, or setup SSH access to any other host.
Configure host address in `/etc/hosts` to `example.com`

Commit changes to your local copy of repo and tag it with a new tag.

Run from environment where Ribosome installed:

    $ ribosome release

    $ ribosome deploy <tag> localhost

    $ ribosome load <tag> webapp dev localhost

To view working site you need to deploy and load
[Django example](https://github.com/alexandervpetrov/ribosome-example-django) project.
