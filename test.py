import google.generativeai as genai
import fitz
from PIL import Image
import io
import tkinter as tk
from tkinter import filedialog, ttk, messagebox
import json
import csv
import threading
import os

def extract_pdf():
    pdf_paths = filedialog.askopenfilenames(filetypes=[("PDF", "*.pdf")])
    if not pdf_paths:
        return
    
    btn_select.config(state="disabled")
    
    # Clear previous tabs
    for tab in notebook.tabs():
        notebook.forget(tab)
    
    file_data.clear()
    
    label_status.config(text=f"Processing {len(pdf_paths)} file(s)...")
    threading.Thread(target=process_pdfs, args=(pdf_paths,), daemon=True).start()

def process_pdfs(pdf_paths):
    total_prompt_tokens = 0
    total_output_tokens = 0
    total_tokens = 0
    
    try:
        api_key = entry_api.get() or "aaa"
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-flash-latest")
        
        for idx, pdf_path in enumerate(pdf_paths, 1):
            try:
                filename = os.path.basename(pdf_path)
                root.after(0, lambda i=idx, total=len(pdf_paths): 
                          label_status.config(text=f"Processing file {i}/{total}..."))
                
                pdf = fitz.open(pdf_path)
                images = [Image.open(io.BytesIO(page.get_pixmap().tobytes())) for page in pdf]
                
                response = model.generate_content([
                    *images,
                    """Extract all subcontractor records. For each field, if data is not found, return empty string "".
Fields:
- contract_number
- agency_name
- contractor_name
- subcontractor_name
- vid_hub_cert
- texas_hub
- total_contract_amount
- paid_this_period
- paid_to_date
- object_code
- payment_app_no
- po_number
- project_name
- utsw_project_no
Return as JSON array with these exact keys."""
                ])
                
                json_text = response.text.strip("```json\n").strip("```")
                data = json.loads(json_text)
                
                # Store data for this file
                file_data[filename] = data
                
                # Create tab for this file
                root.after(0, lambda fn=filename, d=data: create_tab(fn, d))
                
                # Accumulate token usage
                usage = response.usage_metadata
                total_prompt_tokens += usage.prompt_token_count
                total_output_tokens += usage.candidates_token_count
                total_tokens += usage.total_token_count
                
            except Exception as e:
                error_msg = f"Error processing {os.path.basename(pdf_path)}: {str(e)}"
                root.after(0, lambda msg=error_msg: messagebox.showwarning("File Error", msg))
        
        usage_text = f"Tokens: {total_tokens:,} (Input: {total_prompt_tokens:,} | Output: {total_output_tokens:,})"
        if total_tokens > 900000:
            usage_text += "High usage"
        
        total_records = sum(len(d) for d in file_data.values())
        root.after(0, lambda: label_usage.config(text=usage_text))
        root.after(0, lambda: label_status.config(text=f"Completed: {total_records} records from {len(pdf_paths)} file(s)"))
        
    except Exception as e:
        if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
            root.after(0, lambda: messagebox.showerror("Rate Limit", "Rate limit reached. Wait and retry."))
        else:
            root.after(0, lambda: messagebox.showerror("Error", str(e)))
    finally:
        root.after(0, lambda: btn_select.config(state="normal"))

def create_tab(filename, data):
    # Create frame for this tab
    tab_frame = tk.Frame(notebook)
    notebook.add(tab_frame, text=filename)
    
    # Create scrollbars
    scroll_x = tk.Scrollbar(tab_frame, orient="horizontal")
    scroll_y = tk.Scrollbar(tab_frame, orient="vertical")
    
    # Create treeview
    tree = ttk.Treeview(tab_frame, columns=columns, show="headings", 
                        xscrollcommand=scroll_x.set, yscrollcommand=scroll_y.set)
    
    for col in columns:
        tree.heading(col, text=col.replace("_", " ").title())
        tree.column(col, width=120)
    
    scroll_x.config(command=tree.xview)
    scroll_y.config(command=tree.yview)
    
    # Pack widgets
    tree.pack(side="left", fill="both", expand=True)
    scroll_y.pack(side="right", fill="y")
    scroll_x.pack(side="bottom", fill="x")
    
    # Populate data
    for row in data:
        tree.insert("", "end", values=tuple(row.values()))

def export_current_csv():
    current_tab = notebook.select()
    if not current_tab:
        messagebox.showwarning("Warning", "No file selected")
        return
    
    tab_text = notebook.tab(current_tab, "text")
    
    if tab_text not in file_data:
        return
    
    data = file_data[tab_text]
    default_name = tab_text.replace(".pdf", ".csv")
    
    file_path = filedialog.asksaveasfilename(
        defaultextension=".csv", 
        initialfile=default_name,
        filetypes=[("CSV", "*.csv")]
    )
    if not file_path:
        return
    
    try:
        with open(file_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=columns)
            writer.writeheader()
            writer.writerows(data)
        messagebox.showinfo("Success", f"Exported {len(data)} records")
    except Exception as e:
        messagebox.showerror("Export Error", str(e))

def export_all_csv():
    if not file_data:
        messagebox.showwarning("Warning", "No data to export")
        return
    
    folder = filedialog.askdirectory(title="Select folder to save CSV files")
    if not folder:
        return
    
    try:
        for filename, data in file_data.items():
            csv_name = filename.replace(".pdf", ".csv")
            csv_path = os.path.join(folder, csv_name)
            
            with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=columns)
                writer.writeheader()
                writer.writerows(data)
        
        messagebox.showinfo("Success", f"Exported {len(file_data)} CSV files to {folder}")
    except Exception as e:
        messagebox.showerror("Export Error", str(e))

file_data = {}
columns = ("contract_number", "agency_name", "contractor_name", "subcontractor_name", 
           "vid_hub_cert", "texas_hub", "total_contract_amount", "paid_this_period",
           "paid_to_date", "object_code", "payment_app_no", "po_number", "project_name", "utsw_project_no")

root = tk.Tk()
root.title("PDF Extractor (Multi-File with Tabs)")
root.geometry("1300x650")

# Top section
tk.Label(root, text="API Key:").pack(pady=5)
entry_api = tk.Entry(root, width=50)
entry_api.insert(0, "aaa")
entry_api.pack()

btn_select = tk.Button(root, text="Select PDF Files", command=extract_pdf)
btn_select.pack(pady=10)

label_status = tk.Label(root, text="Ready", fg="green")
label_status.pack(pady=2)

label_usage = tk.Label(root, text="Usage: -", fg="blue")
label_usage.pack(pady=3)

notebook = ttk.Notebook(root)
notebook.pack(fill="both", expand=True, padx=10, pady=10)

btn_frame = tk.Frame(root)
btn_frame.pack(pady=5)

tk.Button(btn_frame, text="Export Current Tab to CSV", command=export_current_csv).pack(side="left", padx=5)
tk.Button(btn_frame, text="Export All to CSV", command=export_all_csv).pack(side="left", padx=5)

root.mainloop()
