# 🏗️ Microsoft Fabric OneLake Migration Setup Guide

## Overview
This guide helps you migrate your downloaded SharePoint files to Microsoft Fabric OneLake for advanced analytics.

## Prerequisites

### 1. Microsoft Fabric Access
- ✅ Microsoft Fabric license (Premium or Fabric capacity)
- ✅ Access to a Fabric workspace
- ✅ Permission to create Lakehouses

### 2. Required Information
You need to gather the following IDs from your Fabric environment:

#### Fabric Workspace ID
1. Go to [Microsoft Fabric Portal](https://app.fabric.microsoft.com)
2. Navigate to your workspace
3. Copy the workspace ID from the URL: `https://app.fabric.microsoft.com/groups/{WORKSPACE_ID}/`

#### Fabric Lakehouse ID  
1. In your Fabric workspace, create or navigate to a Lakehouse
2. Copy the Lakehouse ID from the URL: `https://app.fabric.microsoft.com/groups/{WORKSPACE_ID}/items/{LAKEHOUSE_ID}`

## Configuration Steps

### Step 1: Update .env File
Add your Fabric details to the `.env` file:

```properties
# Microsoft Fabric OneLake Configuration
FABRIC_WORKSPACE_ID=12345678-1234-1234-1234-123456789abc
FABRIC_LAKEHOUSE_ID=87654321-4321-4321-4321-cba987654321
ONELAKE_BASE_PATH=/Files/SharePoint_Invoices
DELTA_TABLE_NAME=sharepoint_invoices
```

### Step 2: App Registration Permissions
Your existing Azure AD app registration needs additional permissions for Fabric:

1. Go to [Azure Portal](https://portal.azure.com) → App Registrations
2. Find your app: `74ab6fe0-38a7-45c4-8fe4-512e5dc28a85`
3. Add API permissions:
   - **Power BI Service** → Application permissions → `App.ReadWrite.All`
   - **Microsoft Graph** → Application permissions → `Files.ReadWrite.All`

### Step 3: Test Migration
Run the analysis first to understand your data:

```bash
# Analyze files only (no migration)
python onelake_migrator.py --analyze-only --source "C:/commercial_pdfs/downloaded_files"
```

## Migration Features

### 🔍 File Analysis
- **File inventory**: Count, size, types
- **Cost estimation**: OneLake storage costs
- **Migration planning**: Batch sizes, duration estimates

### 📊 Metadata Extraction
Creates rich metadata for each file:
- File properties (size, dates, checksums)
- Document classification (Invoice, Receipt, Contract, etc.)
- Folder structure preservation
- MIME type detection

### 🚀 Bulk Transfer
- **Batched uploads**: Configurable batch sizes
- **Progress tracking**: Resume interrupted migrations
- **Error handling**: Retry failed uploads
- **Token management**: Automatic renewal

### 🏗️ Delta Lake Integration
- **Structured metadata**: Queryable file catalog
- **Version control**: Delta Lake ACID properties
- **Analytics ready**: Direct integration with Fabric notebooks

## Usage Examples

### Full Migration
```bash
# Run complete migration
python onelake_migrator.py --source "C:/commercial_pdfs/downloaded_files" --batch-size 50

# Resume interrupted migration
python onelake_migrator.py --resume --source "C:/commercial_pdfs/downloaded_files"
```

### Analysis Only
```bash
# Just analyze without migrating
python onelake_migrator.py --analyze-only
```

## Expected Results

### OneLake Structure
```
/Files/SharePoint_Invoices/
├── Plant Invoices/
│   ├── P4/
│   │   ├── invoice1.pdf
│   │   └── invoice2.pdf
│   └── P5/
├── Other_Documents/
└── delta_tables/
    └── sharepoint_invoices/
        └── metadata.parquet
```

### Delta Lake Table
A queryable table with metadata:
```sql
SELECT 
    document_type,
    COUNT(*) as file_count,
    SUM(file_size_bytes)/1024/1024/1024 as total_gb
FROM sharepoint_invoices 
GROUP BY document_type
ORDER BY total_gb DESC
```

## Fabric Analytics Integration

Once migrated, you can:

### 1. Create Fabric Notebooks
```python
# Read the file metadata
df = spark.read.table("sharepoint_invoices")

# Analyze document types
df.groupBy("document_type").count().display()

# Find large files
df.filter(df.file_size_bytes > 10*1024*1024).display()
```

### 2. Build Power BI Reports
- Connect to the Delta table
- Create visualizations of file inventory
- Monitor migration progress
- Track document types and sizes

### 3. Set up Data Pipelines
- Automated file processing
- Document AI integration
- Compliance monitoring
- Backup scheduling

## Troubleshooting

### Common Issues

**Permission Errors**
- Verify app registration permissions
- Check Fabric workspace access
- Ensure lakehouse creation rights

**Token Expiration**
- App registration secrets expire
- Refresh tokens automatically handled
- Check Azure AD app status

**Large File Uploads**
- Use smaller batch sizes for large files
- Monitor network connectivity
- Consider OneLake file size limits

**Memory Issues**
- Large file lists may cause memory errors
- Increase batch processing
- Use streaming for metadata extraction

## Cost Considerations

### OneLake Storage Pricing
- **Standard**: ~$0.023/GB/month
- **Archive**: ~$0.002/GB/month (after 30 days)

### Estimated Costs for Your Data
Based on analysis, your migration will cost approximately:
- **376,882 files** (~500GB estimated)
- **Monthly cost**: ~$11.50/month
- **Annual cost**: ~$138/year

### Cost Optimization
- Use archival policies for old files
- Implement retention policies
- Consider file deduplication

## Next Steps

1. **Get Fabric workspace details** and update `.env`
2. **Test with small batch** to verify connectivity
3. **Run full analysis** to understand scope
4. **Execute migration** in production
5. **Set up Fabric analytics** for insights

## Support

For issues with this migration tool:
1. Check logs in `migration_progress.json`
2. Review failed files in migration logs
3. Test individual file uploads
4. Verify Fabric permissions and quotas
