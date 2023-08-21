check:
	poetry lock --check

setup:
	poetry install

test-devnet:
	poetry run pytest --net=devnet --disable-warnings -s --client=full_node

format:
	poetry run black pragma/
	poetry run isort pragma/
	poetry run autoflake . -r -cd -i

format-check:
	poetry run black pragma/ --check
	poetry run isort pragma/ --check
	poetry run autoflake . -r -cd