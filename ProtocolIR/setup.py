"""Setup configuration for ProtocolIR package."""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()

with open("requirements.txt", "r", encoding="utf-8") as f:
    requirements = [line.strip() for line in f if line.strip() and not line.startswith("#")]

setup(
    name="protocolir",
    version="2.0.0",
    author="ProtocolIR Team",
    author_email="hack@scsp.ai",
    description="Reward-Guided Protocol Compiler for Safe Lab Automation",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/scsp/ProtocolIR",
    packages=find_packages(),
    py_modules=["main"],
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Development Status :: 4 - Beta",
        "Intended Audience :: Science/Research",
        "Topic :: Scientific/Engineering :: Bio-Informatics",
    ],
    python_requires=">=3.9",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "protocolir=main:main",
        ],
    },
)
