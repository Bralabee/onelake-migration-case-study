#!/usr/bin/env python3
"""
🏗️ Microsoft Fabric OneLake Migration Tool
==========================================

Migrate downloaded SharePoint files to Microsoft Fabric OneLake Delta Lake
for advanced analytics and data processing.

Features:
- Bulk file transfer to OneLake
- Delta Lake table creation
- Metadata extraction and cataloging
- Progress tracking and resumption
- File organization by type/date
- Integration with Fabric workspaces

Author: GitHub Copilot
Date: August 7, 2025
"""

import os
import json
import shutil
from datetime import datetime
from pathlib import Path
import logging
import pandas as pd
from typing import Dict, List, Any, Optional
import requests
import mimetypes
import hashlib
import time
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class OneLakeMigrator:
    """Microsoft Fabric OneLake migration tool."""
    
    def __init__(self, source_path: str, config: Dict[str, str]):
        """
        Initialize the OneLake migrator.
        
        Args:
            source_path: Path to downloaded files
            config: Configuration with Fabric workspace details
        """
        self.source_path = Path(source_path)
        self.config = config
        
        # OneLake configuration
        self.workspace_id = config.get("fabric_workspace_id")
        self.lakehouse_id = config.get("fabric_lakehouse_id") 
        self.tenant_id = config.get("tenant_id")
        self.client_id = config.get("client_id")
        self.client_secret = config.get("client_secret")
        
        # Migration paths
        self.onelake_base_path = config.get("onelake_base_path", "/Files/SharePoint_Invoices")
        self.delta_table_name = config.get("delta_table_name", "sharepoint_invoices")
        
        # Progress tracking
        self.migration_log = Path("migration_progress.json")
        self.metadata_file = Path("file_metadata.json")
        
    def get_fabric_token(self) -> str:
        """Get access token for Microsoft Fabric."""
        token_url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
        token_data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": "https://api.fabric.microsoft.com/.default"
        }
        
        response = requests.post(token_url, data=token_data)
        response.raise_for_status()
        return response.json()["access_token"]
    
    def analyze_source_files(self) -> Dict[str, Any]:
        """Analyze source files and create migration plan."""
        logger.info("📊 Analyzing source files for migration...")
        
        analysis = {
            "total_files": 0,
            "total_size_gb": 0,
            "file_types": {},
            "directory_structure": {},
            "migration_estimate": {},
            "files_by_date": {},
            "largest_files": []
        }
        
        if not self.source_path.exists():
            logger.error(f"❌ Source path does not exist: {self.source_path}")
            return analysis
        
        file_list = []
        
        for file_path in self.source_path.rglob("*"):
            if file_path.is_file():
                try:
                    stat = file_path.stat()
                    size_bytes = stat.st_size
                    
                    # File info
                    file_info = {
                        "path": str(file_path),
                        "relative_path": str(file_path.relative_to(self.source_path)),
                        "name": file_path.name,
                        "size_bytes": size_bytes,
                        "size_mb": size_bytes / (1024 * 1024),
                        "extension": file_path.suffix.lower(),
                        "mime_type": mimetypes.guess_type(str(file_path))[0],
                        "created_date": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                        "modified_date": datetime.fromtimestamp(stat.st_mtime).isoformat()
                    }
                    
                    file_list.append(file_info)
                    
                    # Update analysis
                    analysis["total_files"] += 1
                    analysis["total_size_gb"] += size_bytes / (1024**3)
                    
                    # File types
                    ext = file_path.suffix.lower()
                    if ext not in analysis["file_types"]:
                        analysis["file_types"][ext] = {"count": 0, "size_gb": 0}
                    analysis["file_types"][ext]["count"] += 1
                    analysis["file_types"][ext]["size_gb"] += size_bytes / (1024**3)
                    
                    # Directory structure
                    parent_dir = str(file_path.parent.relative_to(self.source_path))
                    if parent_dir not in analysis["directory_structure"]:
                        analysis["directory_structure"][parent_dir] = {"count": 0, "size_gb": 0}
                    analysis["directory_structure"][parent_dir]["count"] += 1
                    analysis["directory_structure"][parent_dir]["size_gb"] += size_bytes / (1024**3)
                    
                except Exception as e:
                    logger.warning(f"⚠️ Error analyzing {file_path}: {e}")
        
        # Migration estimates
        analysis["migration_estimate"] = {
            "estimated_duration_hours": analysis["total_size_gb"] / 10,  # ~10GB/hour estimate
            "onelake_storage_cost_estimate": f"${analysis['total_size_gb'] * 0.023:.2f}/month",  # Rough estimate
            "recommended_batch_size": min(1000, analysis["total_files"] // 10)
        }
        
        # Top file types by size
        analysis["top_file_types"] = sorted(
            analysis["file_types"].items(),
            key=lambda x: x[1]["size_gb"],
            reverse=True
        )[:10]
        
        # Save analysis
        with open("migration_analysis.json", "w") as f:
            json.dump(analysis, f, indent=2)
        
        logger.info(f"✅ Analysis complete: {analysis['total_files']:,} files, {analysis['total_size_gb']:.2f} GB")
        return analysis
    
    def create_migration_batches(self, batch_size: int = 100) -> List[List[Dict]]:
        """Create batches of files for migration."""
        logger.info(f"📦 Creating migration batches (size: {batch_size})...")
        
        file_list = []
        for file_path in self.source_path.rglob("*"):
            if file_path.is_file():
                file_list.append({
                    "source_path": str(file_path),
                    "relative_path": str(file_path.relative_to(self.source_path)),
                    "size_bytes": file_path.stat().st_size
                })
        
        # Sort by size (smaller files first for faster initial progress)
        file_list.sort(key=lambda x: x["size_bytes"])
        
        batches = []
        for i in range(0, len(file_list), batch_size):
            batches.append(file_list[i:i + batch_size])
        
        logger.info(f"📦 Created {len(batches)} batches")
        return batches
    
    def upload_to_onelake(self, file_path: str, onelake_path: str, token: str) -> bool:
        """Upload a single file to OneLake."""
        try:
            # OneLake REST API endpoint
            api_base = "https://api.fabric.microsoft.com/v1"
            upload_url = f"{api_base}/workspaces/{self.workspace_id}/items/{self.lakehouse_id}/files{onelake_path}"
            
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/octet-stream"
            }
            
            with open(file_path, 'rb') as f:
                response = requests.put(upload_url, headers=headers, data=f)
                response.raise_for_status()
                
            logger.info(f"✅ Uploaded: {onelake_path}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Upload failed for {file_path}: {e}")
            return False
    
    def create_delta_table_metadata(self, file_list: List[Dict]) -> pd.DataFrame:
        """Create metadata DataFrame for Delta Lake table."""
        logger.info("📋 Creating Delta Lake metadata...")
        
        metadata_records = []
        
        for file_info in file_list:
            file_path = Path(file_info["source_path"])
            
            try:
                stat = file_path.stat()
                
                # Extract metadata
                record = {
                    "file_id": hashlib.md5(str(file_path).encode()).hexdigest(),
                    "file_name": file_path.name,
                    "file_path": file_info["relative_path"],
                    "onelake_path": f"{self.onelake_base_path}/{file_info['relative_path']}",
                    "file_size_bytes": stat.st_size,
                    "file_extension": file_path.suffix.lower(),
                    "mime_type": mimetypes.guess_type(str(file_path))[0],
                    "created_date": datetime.fromtimestamp(stat.st_ctime),
                    "modified_date": datetime.fromtimestamp(stat.st_mtime),
                    "migration_date": datetime.now(),
                    "migration_status": "pending",
                    "checksum": self.calculate_file_checksum(file_path),
                    "source_system": "SharePoint",
                    "document_type": self.classify_document_type(file_path.name),
                    "folder_structure": str(file_path.parent.relative_to(self.source_path))
                }
                
                metadata_records.append(record)
                
            except Exception as e:
                logger.warning(f"⚠️ Error creating metadata for {file_path}: {e}")
        
        df = pd.DataFrame(metadata_records)
        return df
    
    def calculate_file_checksum(self, file_path: Path) -> str:
        """Calculate MD5 checksum for file integrity."""
        try:
            hash_md5 = hashlib.md5()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except:
            return None
    
    def classify_document_type(self, filename: str) -> str:
        """Classify document type based on filename patterns."""
        filename_lower = filename.lower()
        
        if "invoice" in filename_lower:
            return "Invoice"
        elif "receipt" in filename_lower:
            return "Receipt"
        elif "contract" in filename_lower:
            return "Contract"
        elif "statement" in filename_lower:
            return "Statement"
        elif filename_lower.endswith(('.pdf', '.doc', '.docx')):
            return "Document"
        elif filename_lower.endswith(('.xls', '.xlsx', '.csv')):
            return "Spreadsheet"
        elif filename_lower.endswith(('.jpg', '.jpeg', '.png', '.tiff')):
            return "Image"
        else:
            return "Other"
    
    def save_progress(self, progress_data: Dict):
        """Save migration progress."""
        with open(self.migration_log, 'w') as f:
            json.dump(progress_data, f, indent=2, default=str)
    
    def load_progress(self) -> Dict:
        """Load previous migration progress."""
        if self.migration_log.exists():
            with open(self.migration_log, 'r') as f:
                return json.load(f)
        return {"completed_batches": [], "failed_files": [], "last_batch": 0}
    
    def migrate_files(self, batch_size: int = 100, resume: bool = True) -> Dict[str, Any]:
        """Main migration function."""
        logger.info("🚀 Starting OneLake migration...")
        
        # Load progress if resuming
        progress = self.load_progress() if resume else {"completed_batches": [], "failed_files": [], "last_batch": 0}
        
        # Create batches
        batches = self.create_migration_batches(batch_size)
        start_batch = progress.get("last_batch", 0)
        
        logger.info(f"📦 Migrating {len(batches)} batches (starting from batch {start_batch})")
        
        # Get authentication token
        token = self.get_fabric_token()
        
        migration_stats = {
            "start_time": datetime.now(),
            "total_files": sum(len(batch) for batch in batches),
            "processed_files": 0,
            "successful_uploads": 0,
            "failed_uploads": 0,
            "batches_completed": len(progress["completed_batches"])
        }
        
        # Process batches
        for batch_idx, batch in enumerate(batches[start_batch:], start_batch):
            logger.info(f"📦 Processing batch {batch_idx + 1}/{len(batches)} ({len(batch)} files)")
            
            batch_success = True
            
            for file_info in batch:
                source_path = file_info["source_path"]
                relative_path = file_info["relative_path"]
                onelake_path = f"{self.onelake_base_path}/{relative_path}"
                
                # Upload file
                success = self.upload_to_onelake(source_path, onelake_path, token)
                
                migration_stats["processed_files"] += 1
                
                if success:
                    migration_stats["successful_uploads"] += 1
                else:
                    migration_stats["failed_uploads"] += 1
                    progress["failed_files"].append({
                        "file": source_path,
                        "error": "Upload failed",
                        "timestamp": datetime.now().isoformat()
                    })
                    batch_success = False
                
                # Progress update
                if migration_stats["processed_files"] % 50 == 0:
                    pct = (migration_stats["processed_files"] / migration_stats["total_files"]) * 100
                    logger.info(f"📊 Progress: {pct:.1f}% ({migration_stats['processed_files']}/{migration_stats['total_files']})")
            
            # Mark batch as completed
            if batch_success:
                progress["completed_batches"].append(batch_idx)
                migration_stats["batches_completed"] += 1
            
            progress["last_batch"] = batch_idx + 1
            
            # Save progress every batch
            self.save_progress(progress)
            
            # Token refresh (every hour)
            if batch_idx % 100 == 0 and batch_idx > 0:
                token = self.get_fabric_token()
        
        migration_stats["end_time"] = datetime.now()
        migration_stats["duration"] = migration_stats["end_time"] - migration_stats["start_time"]
        
        logger.info("✅ Migration completed!")
        logger.info(f"📊 Results: {migration_stats['successful_uploads']}/{migration_stats['total_files']} files migrated")
        
        return migration_stats
    
    def create_delta_table(self, metadata_df: pd.DataFrame) -> bool:
        """Create Delta Lake table with file metadata."""
        logger.info("🏗️ Creating Delta Lake table...")
        
        try:
            # Save metadata as Parquet (Delta Lake compatible)
            delta_path = f"delta_tables/{self.delta_table_name}"
            os.makedirs(delta_path, exist_ok=True)
            
            metadata_df.to_parquet(f"{delta_path}/metadata.parquet", index=False)
            
            # Create Delta Lake table definition
            table_sql = f"""
            CREATE TABLE IF NOT EXISTS {self.delta_table_name} (
                file_id STRING,
                file_name STRING,
                file_path STRING,
                onelake_path STRING,
                file_size_bytes BIGINT,
                file_extension STRING,
                mime_type STRING,
                created_date TIMESTAMP,
                modified_date TIMESTAMP,
                migration_date TIMESTAMP,
                migration_status STRING,
                checksum STRING,
                source_system STRING,
                document_type STRING,
                folder_structure STRING
            )
            USING DELTA
            LOCATION '{delta_path}'
            """
            
            # Save SQL for manual execution in Fabric
            with open(f"{self.delta_table_name}_create_table.sql", "w") as f:
                f.write(table_sql)
            
            logger.info(f"✅ Delta table definition saved: {self.delta_table_name}_create_table.sql")
            return True
            
        except Exception as e:
            logger.error(f"❌ Delta table creation failed: {e}")
            return False

def load_fabric_config() -> Dict[str, str]:
    """Load Microsoft Fabric configuration."""
    config = {
        # From existing .env file
        "tenant_id": os.environ.get("TENANT_ID", ""),
        "client_id": os.environ.get("CLIENT_ID", ""),
        "client_secret": os.environ.get("CLIENT_SECRET", ""),
        
        # Fabric-specific settings (you'll need to add these)
        "fabric_workspace_id": os.environ.get("FABRIC_WORKSPACE_ID", ""),
        "fabric_lakehouse_id": os.environ.get("FABRIC_LAKEHOUSE_ID", ""),
        "onelake_base_path": os.environ.get("ONELAKE_BASE_PATH", "/Files/SharePoint_Invoices"),
        "delta_table_name": os.environ.get("DELTA_TABLE_NAME", "sharepoint_invoices")
    }
    
    return config

def main():
    """Main function for OneLake migration."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Microsoft Fabric OneLake Migration Tool")
    parser.add_argument("--source", default="C:/commercial_pdfs/downloaded_files",
                       help="Source directory with downloaded files")
    parser.add_argument("--analyze-only", action="store_true",
                       help="Only analyze files, don't migrate")
    parser.add_argument("--batch-size", type=int, default=100,
                       help="Number of files per batch")
    parser.add_argument("--resume", action="store_true",
                       help="Resume previous migration")
    
    args = parser.parse_args()
    
    # Load configuration
    config = load_fabric_config()
    
    # Validate configuration
    required_fields = ["tenant_id", "client_id", "client_secret", "fabric_workspace_id", "fabric_lakehouse_id"]
    missing = [field for field in required_fields if not config.get(field)]
    
    if missing:
        logger.error(f"❌ Missing configuration: {missing}")
        logger.info("💡 Add these to your .env file:")
        for field in missing:
            logger.info(f"   {field.upper()}=your_value_here")
        return
    
    # Create migrator
    migrator = OneLakeMigrator(args.source, config)
    
    # Analyze files
    analysis = migrator.analyze_source_files()
    
    print("\n🏗️ MIGRATION ANALYSIS")
    print("=" * 50)
    print(f"📁 Source Directory: {args.source}")
    print(f"📊 Total Files: {analysis['total_files']:,}")
    print(f"💾 Total Size: {analysis['total_size_gb']:.2f} GB")
    print(f"⏱️  Estimated Duration: {analysis['migration_estimate']['estimated_duration_hours']:.1f} hours")
    print(f"💰 Estimated Storage Cost: {analysis['migration_estimate']['onelake_storage_cost_estimate']}")
    
    print(f"\n📋 Top File Types:")
    for ext, data in analysis["top_file_types"][:5]:
        print(f"  • {ext or 'No extension'}: {data['count']:,} files ({data['size_gb']:.2f} GB)")
    
    if args.analyze_only:
        logger.info("📊 Analysis complete. Use --migrate to start migration.")
        return
    
    # Confirm migration
    response = input(f"\n🚀 Proceed with migration to OneLake? (y/N): ")
    if response.lower() != 'y':
        logger.info("Migration cancelled.")
        return
    
    # Start migration
    results = migrator.migrate_files(args.batch_size, args.resume)
    
    print("\n✅ MIGRATION COMPLETE")
    print("=" * 50)
    print(f"📊 Files Processed: {results['processed_files']:,}")
    print(f"✅ Successful: {results['successful_uploads']:,}")
    print(f"❌ Failed: {results['failed_uploads']:,}")
    print(f"⏱️  Duration: {results['duration']}")

if __name__ == "__main__":
    main()
