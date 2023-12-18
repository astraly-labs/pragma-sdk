from setuptools import find_packages, setup

setup(
    name="pragma-sdk",
    version="0.1.0",
    packages=find_packages(),
    entry_points={
        "console_scripts": [
            "pragma-cli=cli.random:main",
        ],
    },
    install_requires=[
        "argparse",  # Note: argparse is included in the standard library since Python 2.7 and Python 3.2
    ],
)
