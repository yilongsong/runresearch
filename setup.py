from setuptools import setup, find_packages

setup(
    name="runresearch",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "pyyaml",
        "textual",
    ],
    entry_points={
        "console_scripts": [
            "runresearch=runresearch.cli:main",
        ],
    },
)
