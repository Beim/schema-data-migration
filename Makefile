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

single_test:
	pip install .
	python -m pytest ./tests -k $(t)

collect:
	pip install .
	python -m pytest --collect-only ./tests

build-image:
	sudo docker build -t beim/schema-data-migration:0.5.4 .
	sudo docker build -t beim/schema-data-migration:latest .
