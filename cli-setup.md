# 🛠 SPECTRA CLI Setup Guide

Welcome to the **SPECTRA CLI**! This guide will walk you through the process of setting up, configuring, and running the interactive terminal-based AI pipeline that audits your local codebases and generates professional Markdown and PDF reports.

---

## 📋 Prerequisites

Before you install the CLI, ensure you have the following installed on your system:
- **Python 3.12+**
- **Git**
- An **OpenAI API Key** (you can generate one at [OpenAI Platform](https://platform.openai.com/api-keys))

---

## 🚀 Installation & Setup

Since this CLI is written in Python, you can easily install it globally within your virtual environment so you can run the `spectra` command anywhere within your terminal session.

### Option 1: One-Command Public Installation (Recommended)
If the repository is public, you can install the CLI directly from GitHub using `pip` without needing to clone the source code manually:
```bash
pip install git+https://github.com/Aashutosh-Mahajan/codebase-audit-agent.git
```

### Option 2: Manual Clone & Install
If you want to develop or modify the tool:

**1. Clone the Repository**
```bash
git clone https://github.com/Aashutosh-Mahajan/codebase-audit-agent.git
cd codebase-audit-agent
```

**2. Create a Virtual Environment**
It is highly recommended to install the CLI within a virtual environment.
```bash
# Windows
python -m venv venv
.\venv\Scripts\Activate.ps1

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

**3. Install the CLI Package**
Use `pip` to install the package in editable mode. This registers the `spectra` command in your terminal.
```bash
pip install -e .
```

---

## 🎮 How to Use the CLI

The CLI is designed to be interactive, visually appealing, and easy to use.

### 1. View the Help Menu
You can view the detailed help menu at any time by running:
```bash
spectra -help
# or
spectra --help
```

### 2. Run an Audit on Your Current Directory
To start auditing the codebase you are currently in, just run the command without any arguments:
```bash
spectra
```

### 3. Run an Audit on a Specific Directory
If you want to audit a different folder without changing your current directory, use the `-d` (or `--dir`) flag:
```bash
spectra -d /path/to/your/project
```

---

## ⚙️ Configuration & `.spectra` Folder

When you run the `spectra` command for the **first time** in a specific project directory, the CLI will interactively help you configure your environment.

### The Setup Flow:
1. **Logo Animation**: The CLI starts with a sleek ASCII animation.
2. **Directory Creation**: It will automatically create a hidden folder named `.spectra` in the target directory and generate a template `.env` file inside it.
3. **Action Required**: The CLI will pause and instruct you to open `.spectra/.env` in your text editor.
4. **Configuration**: Open the `.env` file, paste your OpenAI API Key (`OPENAI_API_KEY=sk-...`), and confirm or change the selected model (`OPENAI_MODEL=gpt-4o-mini`).
5. **Run Again**: Once you have saved the `.env` file, run `spectra` again to start the audit!

### Where is the configuration saved?
Your configuration is saved locally in `.spectra/.env`. 
The next time you run `spectra` in that same project folder, the CLI will automatically detect this `.env` file and immediately launch the multi-agent audit!

If you ever need to change your API key or Model, you can simply open and edit the `.spectra/.env` file manually.

---

## 📊 Live Progress & Reports

Once the audit starts, you will see a real-time progress bar in your terminal. Behind the scenes, the system dispatches 6 specialized AI agents (Frontend, Backend, Database, Security, DevOps, and Dependency) to analyze your code simultaneously.

When the audit completes, the reports are automatically saved to your local project inside the **`.spectra/reports`** directory. The CLI will output:
1. **Audit Summary**: A breakdown of findings categorized by severity (EXTREME, HIGH, MEDIUM, LOW).
2. **Clickable Links**: Direct file paths to the generated `.md` (Markdown) and `.pdf` reports, which you can Ctrl+Click (or Cmd+Click) to open directly from your terminal!
