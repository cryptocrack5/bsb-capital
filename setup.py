from setuptools import setup, find_packages

setup(
    name="bsb-capital-crypto-analyzer",
    version="1.0.0",
    description="Institutional-grade crypto token analysis platform",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        "numpy>=1.24.0",
        "pandas>=2.0.0",
        "requests>=2.31.0",
        "vaderSentiment>=3.3.2",
        "ta>=0.11.0",
        "arch>=6.0.0",
        "rich>=13.0.0",
        "python-dateutil>=2.8.0",
        "scipy>=1.11.0",
        "scikit-learn>=1.3.0",
        "aiohttp>=3.9.0",
        "pydantic>=2.0.0",
    ],
    entry_points={
        "console_scripts": [
            "bsb-analyze=src.main:main",
        ],
    },
)
