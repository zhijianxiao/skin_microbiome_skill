from setuptools import setup, find_packages

setup(
    name="skinmicrobiome",
    version="0.1.0",
    description="非人类皮肤微生物组文献检索与宏基因组数据集定位工具",
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
            "skinmicrobiome=skill.main:main",
        ],
    },
)
