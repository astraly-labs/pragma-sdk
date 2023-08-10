check:
	poetry lock --check

setup:
	poetry install

test-no-log:
	poetry run pytest tests -n logical

format:
	poetry run black pragma/
	poetry run isort pragma/
	poetry run autoflake . -r

format-check:
	poetry run black pragma/ --check
	poetry run isort pragma/ --check
	poetry run autoflake . -r -cd