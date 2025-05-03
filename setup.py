from setuptools import setup, find_packages

setup(
    name="aiperf",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "aiohttp>=3.8.0",
        "pydantic>=2.0.0",
        "pyyaml>=6.0.0",
        "pytest>=7.0.0",
        "pytest-asyncio>=0.20.0",
        "pytest-mock",
        "pytest-cov",
        "pytest-xdist",
        "pyzmq>=24.0.0",
        "numpy>=1.22.0",
        "pandas>=1.4.0",
        "kubernetes>=25.0.0",
        "requests>=2.28.0",
        "prometheus-client>=0.14.0",
        "click>=8.0.0",
        "tqdm>=4.64.0",
    ],
) 