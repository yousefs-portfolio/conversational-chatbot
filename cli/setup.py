"""Setup script for the Conversational AI CLI."""

from setuptools import setup, find_packages

setup(
    name="conversational-cli",
    version="1.0.0",
    description="Command-line interface for Conversational AI system",
    author="Conversational AI Team",
    packages=find_packages(),
    install_requires=[
        "click>=8.0.0",
        "httpx>=0.25.0",
        "rich>=13.0.0",
        "python-dotenv>=1.0.0",
        "pydantic>=2.0.0",
        "tabulate>=0.9.0",
    ],
    entry_points={
        "console_scripts": [
            "conversational=cli:main",
        ],
    },
    python_requires=">=3.11",
)