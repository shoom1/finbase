"""
Setup script for finbase package.

This allows finbase to be installed as a Python package for use by other projects.
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read the long description from README
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text()

setup(
    name="finbase",
    version="0.1.1",
    description="Historical financial data management system with support for equities, indices, and multi-asset data",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="FinBase Contributors",
    url="https://github.com/yourusername/finbase",  # Update with actual GitHub URL
    license="MIT",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    include_package_data=True,
    install_requires=[
        "yfinance>=0.2.66",
        "pandas>=1.5.0",
        "numpy>=1.20.0",
        "lxml>=4.9.0",
        "html5lib>=1.1",
        "beautifulsoup4>=4.11.0",
        "requests>=2.28.0",
        "pyyaml>=6.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
        ],
        "dashboard": [
            "streamlit>=1.28.0",
            "plotly>=5.17.0",
        ],
    },
    python_requires=">=3.12",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Financial and Insurance Industry",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.12",
        "Topic :: Office/Business :: Financial",
        "Topic :: Scientific/Engineering",
    ],
    keywords="finance, data, timeseries, equity, index, historical-data",
    project_urls={
        "Bug Reports": "https://github.com/yourusername/finbase/issues",
        "Source": "https://github.com/yourusername/finbase",
        "Documentation": "https://github.com/yourusername/finbase/blob/main/CLAUDE.md",
    },
)
