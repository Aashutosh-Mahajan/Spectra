from setuptools import setup, find_packages

setup(
    name="spectra",
    version="1.0.4",
    packages=find_packages(),
    py_modules=["cli"],
    include_package_data=True,
    install_requires=[
        "click",
        "rich",
        "python-dotenv>=1.1.0",
        "fastapi>=0.115.0",
        "uvicorn[standard]>=0.34.0",
        "pydantic>=2.10.0",
        "langgraph>=0.4.0",
        "langchain-openai>=0.3.0",
        "langchain-core>=0.3.0",
        "langchain-community>=0.3.0",
        "gitpython>=3.1.44",
        "markdown>=3.7",
        "xhtml2pdf>=0.2.17",
        "pygments>=2.19.0",
        "streamlit>=1.42.0",
        "requests>=2.32.0",
        "httpx>=0.27.0",
        "tiktoken>=0.9.0",
        "faiss-cpu>=1.7.0",
        "rank_bm25>=0.2.2",
    ],
    extras_require={
        "test": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.23.0",
            "pytest-cov>=4.1.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "spectra=cli:main",
        ],
    },
)
