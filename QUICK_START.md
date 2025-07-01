# Quick Start Guide - AWS to InfoBlox VPC Manager

## 🚀 Setup (One-time)

1. **Run the automated setup script:**
   ```bash
   ./setup.sh
   ```
   
   This script will:
   - Create a Python virtual environment
   - Install all required dependencies
   - Set up configuration files
   - Show you the next steps

2. **Configure InfoBlox connection:**
   ```bash
   nano config.env
   # Add your InfoBlox Grid Master IP, username, etc.
   ```

## 🔒 Safe Testing (ALWAYS START HERE)

**⚠️ IMPORTANT: Always test with `--dry-run` first!**

### 1. Generate Report Only (safest option)
```bash
source venv/bin/activate
python aws_infoblox_vpc_manager.py --report-only
```

### 2. Preview All Changes (dry-run)
```bash
python aws_infoblox_vpc_manager.py --dry-run --sync-all
```

### 3. Preview Missing Networks Only
```bash
python aws_infoblox_vpc_manager.py --dry-run --create-missing
```

### 4. Preview Tag Updates Only
```bash
python aws_infoblox_vpc_manager.py --dry-run --update-discrepant
```

## ⚡ Common Usage Examples

### Interactive Mode (safest for beginners)
```bash
python aws_infoblox_vpc_manager.py
# Follow the prompts to choose actions
```

### Command Line Mode (for automation)
```bash
# Test everything first
python aws_infoblox_vpc_manager.py --dry-run --sync-all

# If dry-run looks good, execute the changes
python aws_infoblox_vpc_manager.py --sync-all

# Use specific CSV file
python aws_infoblox_vpc_manager.py --csv-file my_vpcs.csv --dry-run

# Create missing networks only
python aws_infoblox_vpc_manager.py --create-missing

# Update discrepant networks only  
python aws_infoblox_vpc_manager.py --update-discrepant

# Verbose logging for troubleshooting
python aws_infoblox_vpc_manager.py --verbose --dry-run --sync-all
```

## 📋 Step-by-Step Workflow

1. **Setup** (one-time):
   ```bash
   ./setup.sh
   nano config.env  # Add your InfoBlox details
   ```

2. **Test parsing** (verify your CSV works):
   ```bash
   source venv/bin/activate
   python example_usage.py
   ```

3. **Generate report** (see what needs to be done):
   ```bash
   python aws_infoblox_vpc_manager.py --report-only
   ```

4. **Preview changes** (safe - no actual changes):
   ```bash
   python aws_infoblox_vpc_manager.py --dry-run --sync-all
   ```

5. **Execute changes** (when you're confident):
   ```bash
   python aws_infoblox_vpc_manager.py --sync-all
   ```

## 🆘 Help & Options

```bash
python aws_infoblox_vpc_manager.py --help
```

## 🔧 Command Line Options

| Option | Description | Example |
|--------|-------------|---------|
| `--dry-run` | Preview changes without executing | `--dry-run --sync-all` |
| `--report-only` | Generate report only | `--report-only` |
| `--create-missing` | Create missing networks | `--create-missing --dry-run` |
| `--update-discrepant` | Update tag differences | `--update-discrepant --dry-run` |
| `--sync-all` | Both create and update | `--sync-all --dry-run` |
| `--csv-file FILE` | Specify CSV file | `--csv-file my_data.csv` |
| `--network-view VIEW` | Override network view | `--network-view production` |
| `--verbose` | Enable debug logging | `--verbose --dry-run` |

## 🛡️ Safety Features

- **Dry-run mode**: See exactly what would happen before doing it
- **Report-only mode**: Just generate analysis reports
- **Interactive prompts**: Ask for confirmation on important actions
- **Comprehensive logging**: Full audit trail of all operations
- **Error handling**: Graceful handling of network/parsing errors

## 📊 Understanding the Output

### Report Sections:
- **✅ Matching Networks**: VPCs that are properly synchronized
- **🔴 Missing Networks**: VPCs that need to be created in InfoBlox  
- **🟡 Discrepant Networks**: VPCs with different tags/EAs that need updating
- **🔍 Errors**: VPCs that had processing errors

### Dry-run Output:
```
DRY RUN: Would create network 10.212.224.0/23 with comment: AWS VPC: mi-lz-icd-core-team...
DRY RUN: EAs would be: {'aws_name': 'mi-lz-icd-core-team...', 'environment': 'prodpci'}
```

## 🚨 Troubleshooting

### Connection Issues:
```bash
# Test InfoBlox connectivity
python aws_infoblox_vpc_manager.py --report-only --verbose
```

### CSV Parsing Issues:
```bash
# Test your CSV file
python example_usage.py
```

### Permission Issues:
- Ensure your InfoBlox user has network management rights
- Verify network view access permissions

## 📝 Files Generated

- `vpc_comparison_report.md` - Detailed comparison report
- `aws_infoblox_vpc_manager.log` - Complete operation log
- `sample_report.md` - Sample report from example_usage.py

---
**Remember: ALWAYS use `--dry-run` first to preview changes!**
