# Viva Engage Tools

Viva Engage Tools generates Viva Engage membership CSV reports from Oracle data, with optional email delivery.

This project is Windows-only.

You can run it in either mode:
- Web UI (recommended for daily use)
- CLI (recommended for scheduled automation)

## Quick Start

### One-line install

Windows (PowerShell):
```powershell
irm https://raw.githubusercontent.com/xtraorange/viva-engage-tools/main/scripts/install.ps1 | iex
```

The installer clones the repository and sets up a Python virtual environment in:
```
%USERPROFILE%\viva-engage-tools
```
(e.g. `C:\Users\YourName\viva-engage-tools`)

At the end of installation it will prompt you to press any key to launch the server.

### Manual install

1. Install Python 3.10+
2. Clone or download this repository:
```bash
git clone https://github.com/xtraorange/viva-engage-tools.git
cd viva-engage-tools
```
3. Start the app by double-clicking start.bat.

On first run, start.bat will automatically create the virtual environment and install dependencies if needed.

## Web UI Overview

Primary navigation:
- Dashboard
- Generate
- Groups
- Tags
- Settings

Additional pages are available from Settings:
- Ad Hoc Name Matcher
- Email Templates
- Updates
- Backup Configuration
- Restore Configuration

## What the App Does

### Group management
- Create, view, edit, and delete groups
- Configure display name, tags, email recipient, and output directory override
- Define query input using either:
  - Query Builder parameters
  - Manual SQL override (query.sql)
- Persist preferred query mode (builder/manual) per group

### Query Builder
- Build hierarchy queries using block-based configuration:
  - Hierarchy by person
  - Hierarchy by role attributes
  - Filtered population
  - Manual individuals
- Apply filters such as job title, BU, company, branch, and department
- Preview generated SQL
- Test query row count
- Accept builder output back into group editing

### Report generation
- Select groups directly and/or by tags
- Generate CSV reports in parallel
- Optional email delivery:
  - To each group's configured recipient
  - To one override recipient for all selected reports
- Track progress on status page
- View generated report content from status page with in-page pagination

### Tags
- Create, edit, and delete tags
- Assign tags to multiple groups
- Browse group membership for each tag

### Settings
- Configure Oracle connection (TNS)
- Configure output directory and worker count
- Configure email settings:
  - SMTP settings
  - Outlook mode (Windows)
- Restart app from UI
- Reset dashboard statistics

### Email templates
- Manage standard and override email templates

### Ad Hoc Name Matcher
- Upload a CSV of names
- Search/match employees
- Review and adjust selections
- Export enriched results as CSV

### Updates
- Check latest version from GitHub
- Show latest version metadata
- Perform update/force-update workflow
- Stream update progress and request restart

### Backup and restore
- Download zip backup of config and groups
- Restore from backup zip

## CLI Usage

Run CLI mode:
```bash
.venv\Scripts\python.exe run_reports.py --cli
```

Examples:
```bash
# list available groups
python run_reports.py --cli list

# run selected handles
python run_reports.py --cli sales_team accounting_team

# run selected numeric indices
python run_reports.py --cli 1 2 3

# run by tag
python run_reports.py --cli leadership

# email to configured recipients
python run_reports.py --cli sales_team --email

# email all selected reports to one address
python run_reports.py --cli sales_team --email user@example.com
```

## Project Structure

```text
viva-engage-tools/
├── config/
├── groups/
├── src/
│   ├── services/
│   ├── ui/
│   │   ├── routes/
│   │   ├── templates/
│   │   └── static/
│   ├── tests/
│   └── ...
├── run_reports.py
└── requirements.txt
```

## Security Notes

- Backups may contain sensitive configuration values
- Report CSVs may contain sensitive member data
- Protect output folders and backup files appropriately

## Version Management

Version metadata is stored in config/version.yaml.

To release a new version:
1. Update config/version.yaml
2. Commit and push
3. Users can check from the Updates page

## Support

For issues and feature requests, use:
https://github.com/xtraorange/viva-engage-tools