"""Setup configuration for eLife Graph Builder."""

from setuptools import setup, find_packages
from pathlib import Path

# Read README
readme_path = Path(__file__).parent / "README.md"
long_description = readme_path.read_text() if readme_path.exists() else ""

setup(
    name="elife-graph-builder",
    version="0.1.0",
    description="Build citation graphs from eLife articles",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Your Name",
    packages=find_packages(exclude=["tests", "tests.*"]),
    python_requires=">=3.8",
    install_requires=[
        "lxml>=4.9.0",
        "requests>=2.31.0",
        "python-dotenv>=1.0.0",
        "pydantic>=2.0.0",
        "tqdm>=4.66.0",
        "neo4j>=5.14.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-cov>=4.1.0",
            "pytest-mock>=3.12.0",
            "black>=23.0.0",
            "ruff>=0.1.0",
            "mypy>=1.7.0",
        ]
    },
    entry_points={
        "console_scripts": [
            "elife-download-samples=scripts.download_samples:main",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Science/Research",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
)
