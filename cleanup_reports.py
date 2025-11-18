import os

# Define the reports directory
reports_dir = r"c:\Users\ACER\Desktop\arjenappliances_system\myproject\templates\reports"

# List of backup files to remove
backup_files = [
    "reports_exact.html",
    "reports_new.html", 
    "reports_original_design.html",
    "reports_simple.html"
]

# Remove backup files
for file in backup_files:
    file_path = os.path.join(reports_dir, file)
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
            print(f"Removed: {file}")
        except Exception as e:
            print(f"Error removing {file}: {e}")
    else:
        print(f"File not found: {file}")

# List remaining files
print("\nRemaining files in reports directory:")
for file in os.listdir(reports_dir):
    print(f"  {file}")
