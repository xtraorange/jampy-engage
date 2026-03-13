
# Project Structure Refactoring Summary

## 📁 **Directory Organization**

### **Root Level (Clean & Minimal)**
```
viva-engage-tools/
├── run_reports.py          ← Wrapper script for convenience
├── README.md
├── requirements.txt
├── start.bat               ← Single visible Windows launcher
├── scripts/
│   └── install.ps1         ← Internal Windows bootstrap/install script
├── .git/
├── .venv/
├── .gitignore
├── config/                 ← Configuration files (user data)
├── groups/                 ← Group definitions (user data)
├── output/                 ← Generated CSVs (user data)
├── docs/                   ← Documentation & meta files
└── src/                    ← All application code
```

### **src/ Package Structure (Organized by Function)**
```
src/
├── __init__.py
├── run_reports.py          ← Main entry point module
├── generate_reports.py     ← CLI interface & orchestration
│
├── core modules
│   ├── config.py           ← Configuration loading
│   ├── db.py               ← Database abstraction
│   ├── group.py            ← Group model
│   ├── email_template.py   ← Template management
│   ├── email_util.py       ← SMTP sending
│   ├── outlook_util.py     ← Outlook integration
│   └── sql_builder.py      ← SQL query generation
│
├── services/               ← Business logic layer
│   ├── __init__.py
│   ├── config_service.py   ← Configuration management
│   ├── group_service.py    ← Group CRUD operations
│   ├── report_service.py   ← Report generation workflow
│   └── email_service.py    ← Unified email service
│
├── ui/                     ← Web interface package
│   ├── __init__.py
│   ├── utils.py            ← Flask setup helpers
│   ├── templates/          ← HTML templates
│   │   ├── base.html
│   │   ├── index.html
│   │   ├── generate.html
│   │   ├── status.html
│   │   └── ... (10 more templates)
│   └── routes/             ← Route handlers (Flask blueprints)
│       ├── __init__.py
│       ├── main.py         ← Dashboard routes
│       ├── groups.py       ← Group management routes
│       ├── tags.py         ← Tag management routes
│       ├── api.py          ← AJAX/API endpoints
│       └── updates.py      ← Update & template routes
│
├── utils/                  ← Shared utilities
│   ├── __init__.py
│   ├── file_utils.py       ← File operations (backup, etc)
│   └── validation.py       ← Input validation
│
└── tests/                  ← Test files
    ├── test_cli.py
    ├── test_config_and_group.py
    ├── test_db.py
    ├── test_email.py
    ├── test_interactive_email.py
    └── test_ui.py
```

## ✨ **Benefits of This Structure**

### **1. Clarity & Discoverability**
- **Root is clean**: Only startup scripts and meta-files at project root
- **Logical grouping**: Related code is together (all UI stuff in `ui/`, all services in `services/`)
- **Easy navigation**: Know where to look for any functionality

### **2. Better Separation of Concerns**
- **Services layer** - Pure business logic, no Flask dependencies
- **Routes layer** - Flask handlers, minimal logic
- **Utils layer** - Reusable helpers
- **Tests layer** - Co-located with source for easy discovery

### **3. Scalability**
- Can easily add new services without bloating existing ones
- Can reorganize routes without touching business logic
- Tests directory grows with code, stays organized

### **4. Professional Structure**
- Mirrors Django/FastAPI project layouts
- Makes onboarding easier for new developers
- Clear entry points (`run_reports.py` → `src/run_reports.py` → `generate_reports.main()`)

## 🔄 **Migration Details**

### **What Moved**
- ✅ `templates/` → `src/ui/templates/`
- ✅ `tests/` → `src/tests/`
- ✅ `run_reports.py` → `src/run_reports.py` (with root wrapper)
- ✅ `filelist.txt` → `docs/filelist.txt`

### **What Stayed**
- ✅ `config/` - User configuration files
- ✅ `groups/` - User group definitions
- ✅ `output/` - Generated CSV files
- ✅ Root meta files (README, requirements, .git, .venv)

### **Why This Works**
- Root-level `run_reports.py` is a thin wrapper that just imports from `src.run_reports.main()`
- Flask now finds templates at `src/ui/templates/`
- Tests are co-located with source code for better discoverability
- Documentation/meta-files organized in `docs/`
- Windows users only need to double-click `start.bat`; first-run bootstrap is handled automatically

## 🚀 **Entry Points**

### **Web Interface**
```bash
python run_reports.py          # Uses root wrapper, launches web UI
# OR
cd src && python -m generate_reports  # Direct module execution
```

### **CLI**
```bash
python run_reports.py --cli list         # Root wrapper
python run_reports.py group_handle --cli --email  # With email
```

## 📝 **Updated Documentation**
- README.md - Updated with new structure
- `docs/filelist.txt` - Moved for organization

Everything is still functional - this is purely an organizational improvement!
