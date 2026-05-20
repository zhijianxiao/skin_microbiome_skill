from setuptools import setup, find_packages

setup(
    name="skin_microbiome_skill",
    version="0.1.0",
    description="A Python skill for searching, analyzing, and exporting skin microbiome species data",
    packages=find_packages(),
    python_requires=">=3.9",
    install_requires=[
        "biopython",
        "pandas",
        "scispacy",
        "enaBrowserTools",
        "openpyxl",
        "sra-tools",
        "transformers",
        "torch",
    ],
    extras_require={
        "dev": [
            "pytest",
            "pytest-cov",
        ],
    },
    entry_points={
        "console_scripts": [
            "skin-microbiome=skill.main:main",
        ],
    },
)
