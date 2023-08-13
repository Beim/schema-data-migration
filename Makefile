.PHONY: style

check_dirs := tests src

all: style fast_test

style:
	black --preview $(check_dirs)
	isort $(check_dirs)
	flake8 $(check_dirs)

test:
	pip install .
	python -m pytest ./tests

fast_test:
	pip install .
	python -m pytest -m "not slow" ./tests

cov:
	pip install .
	python -m pytest --cov=migration --cov-config=.coveragerc ./tests
cov-html:
	pip install .
	python -m pytest --cov=migration --cov-config=.coveragerc --cov-report=html ./tests

single_test:
	pip install .
	python -m pytest ./tests -k $(t)

collect:
	pip install .
	python -m pytest --collect-only ./tests

build-base-image:
	sudo docker build -f Dockerfile-base -t beim/schema-data-migration:base-0.1.0 .

build-image:
	sudo docker build -f Dockerfile-dev -t beim/schema-data-migration:dev .
