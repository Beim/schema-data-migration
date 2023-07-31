.PHONY: style

check_dirs := tests src

all: style test

style:
	black --preview $(check_dirs)
	isort $(check_dirs)
	flake8 $(check_dirs)

test:
	pip install .
	python -m pytest ./tests

collect:
	pip install .
	python -m pytest --collect-only ./tests

build-image:
	sudo docker build -t beim/schema-data-migration:0.2.0 .
	sudo docker build -t beim/schema-data-migration:latest .
