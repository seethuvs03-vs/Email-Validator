"""Local Windows desktop interface. Run with python app.py."""
import os
import queue
import threading
import tkinter as tk
from collections import Counter
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from email_validator_tool import Cancelled, export_results, read_emails, validate_candidates


class EmailCleaner(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Email Cleaner')
        self.geometry('1080x760')
        self.minsize(840, 620)
        self.configure(bg='#f3f6f8')
        self.results = []
        self.source = None
        self.events = queue.Queue()
        self.cancel = threading.Event()
        self.busy = False
        self.blocklist = None
        self.file = tk.StringVar()
        self.status = tk.StringVar(value='Choose a file to get started.')
        self.filter = tk.StringVar(value='All')
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure('TFrame', background='#f3f6f8')
        style.configure('TLabel', background='#f3f6f8', foreground='#173c49', font=('Segoe UI', 10))
        style.configure('TButton', font=('Segoe UI', 10), padding=(14, 8))
        style.configure('Title.TLabel', font=('Segoe UI', 25, 'bold'))
        style.configure('Primary.TButton', background='#157f78', foreground='white')
        style.map('Primary.TButton', background=[('active', '#116c67'), ('disabled', '#a0b8b6')])
        style.configure('Treeview', rowheight=30, font=('Segoe UI', 10))
        style.configure('Treeview.Heading', font=('Segoe UI', 10, 'bold'))
        outer = ttk.Frame(self, padding=28)
        outer.pack(fill='both', expand=True)
        ttk.Label(outer, text='Email Cleaner', style='Title.TLabel').pack(anchor='w')
        ttk.Label(outer, text='Turn a raw contact file into a clean, organized email list.').pack(anchor='w', pady=(4, 22))
        upload = ttk.LabelFrame(outer, text='  1  Choose your file  ', padding=18)
        upload.pack(fill='x')
        row = ttk.Frame(upload)
        row.pack(fill='x')
        self.entry = ttk.Entry(row, textvariable=self.file, state='readonly')
        self.entry.pack(side='left', fill='x', expand=True, padx=(0, 12))
        self.browse = ttk.Button(row, text='Browse files…', command=self.choose)
        self.browse.pack(side='left')
        ttk.Label(upload, text='Excel (.xlsx, .xls) • Word (.docx) • CSV / TSV • Text', wraplength=750).pack(anchor='w', pady=(10, 3))
        ttk.Label(upload, text='Scans all sheets and Word paragraphs/tables. Email columns also retain malformed entries.', wraplength=850).pack(anchor='w')
        actions = ttk.Frame(outer)
        actions.pack(fill='x', pady=16)
        self.run = ttk.Button(actions, text='Validate emails', style='Primary.TButton', command=self.start)
        self.run.pack(side='left')
        self.stop = ttk.Button(actions, text='Cancel', command=self.stop_work, state='disabled')
        self.stop.pack(side='left', padx=8)
        self.block_button = ttk.Button(actions, text='Add disposable-domain list…', command=self.choose_blocklist)
        self.block_button.pack(side='right')
        self.bar = ttk.Progressbar(outer, mode='determinate')
        self.bar.pack(fill='x')
        ttk.Label(outer, textvariable=self.status, wraplength=950).pack(anchor='w', pady=(8, 14))
        self.counts = tk.StringVar(value='Clean  —     Rejected  —     Needs review  —     Duplicates  —')
        ttk.Label(outer, textvariable=self.counts, font=('Segoe UI', 13, 'bold')).pack(anchor='w', pady=(0, 14))
        controls = ttk.Frame(outer)
        controls.pack(fill='x', pady=(0, 8))
        ttk.Label(controls, text='2  Review results').pack(side='left')
        select = ttk.Combobox(controls, textvariable=self.filter, values=['All', 'Clean', 'Rejected', 'Review', 'Duplicate'], state='readonly', width=16)
        select.pack(side='right')
        select.bind('<<ComboboxSelected>>', lambda _: self.show_results())
        table_frame = ttk.Frame(outer)
        table_frame.pack(fill='both', expand=True)
        self.table = ttk.Treeview(table_frame, columns=('email', 'status', 'reason', 'source'), show='headings')
        for name, width in [('email', 270), ('status', 85), ('reason', 350), ('source', 220)]:
            self.table.heading(name, text=name.title())
            self.table.column(name, width=width, minwidth=70)
        scroll = ttk.Scrollbar(table_frame, orient='vertical', command=self.table.yview)
        horizontal = ttk.Scrollbar(table_frame, orient='horizontal', command=self.table.xview)
        self.table.configure(yscrollcommand=scroll.set, xscrollcommand=horizontal.set)
        self.table.grid(row=0, column=0, sticky='nsew')
        scroll.grid(row=0, column=1, sticky='ns')
        horizontal.grid(row=1, column=0, sticky='ew')
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)
        self.table.bind('<Double-1>', self.details)
        footer = ttk.Frame(outer)
        footer.pack(fill='x', pady=(16, 0))
        self.save = ttk.Button(footer, text='Save Excel + CSV results…', style='Primary.TButton', command=self.export, state='disabled')
        self.save.pack(side='right')
        ttk.Label(footer, text='Preview: first 2,000 matching results. Exports include every result.').pack(side='left')
        ttk.Label(outer, text='Clean = syntax + mail-domain checks passed. Mailbox existence is not guaranteed.\nFiles stay on this computer. DNS queries send domain names only. No emails are sent.', wraplength=940).pack(anchor='w', pady=(16, 0))
        self.protocol('WM_DELETE_WINDOW', self.close)
        self.after(100, self.poll)

    def choose(self):
        path = filedialog.askopenfilename(title='Choose a raw email file', filetypes=[('Supported files', '*.xlsx *.xls *.docx *.csv *.tsv *.txt'), ('All files', '*.*')])
        if path:
            self.file.set(path)
            self.results = []
            self.source = None
            self.show_results()
            self.save.configure(state='disabled')
            self.counts.set('Clean  —     Rejected  —     Needs review  —     Duplicates  —')
            self.status.set('Ready to validate ' + Path(path).name)

    def choose_blocklist(self):
        path = filedialog.askopenfilename(title='One disposable domain per line', filetypes=[('Text list', '*.txt'), ('All files', '*.*')])
        if path:
            self.blocklist = path
            self.block_button.configure(text='Blocklist: ' + Path(path).name)

    def start(self):
        if not Path(self.file.get()).is_file():
            messagebox.showinfo('Choose a file', 'Select an Excel, Word, CSV or text file first.')
            return
        self.results = []
        self.show_results()
        self.save.configure(state='disabled')
        self.source = self.file.get()
        self.cancel.clear()
        self.set_busy(True)
        self.bar.configure(value=0)
        self.counts.set('Reading your file…')
        self.status.set('Extracting email addresses…')
        def work():
            try:
                extra = Path(self.blocklist).read_text(encoding='utf-8-sig').splitlines() if self.blocklist else []
                items = read_emails(self.source, self.cancel)
                self.events.put(('found', len(items)))
                result = validate_candidates(items, lambda n, total: self.events.put(('progress', (n, total))), self.cancel, extra)
                self.events.put(('done', result))
            except Cancelled:
                self.events.put(('cancelled', None))
            except Exception as exc:
                self.events.put(('error', str(exc)))
        threading.Thread(target=work, daemon=True).start()

    def set_busy(self, busy):
        self.busy = busy
        for widget in (self.run, self.browse, self.block_button):
            widget.configure(state='disabled' if busy else 'normal')
        self.stop.configure(state='normal' if busy else 'disabled')

    def stop_work(self):
        self.cancel.set()
        self.stop.configure(state='disabled')
        self.status.set('Cancelling; waiting for active DNS checks to finish…')

    def poll(self):
        try:
            while True:
                kind, data = self.events.get_nowait()
                if kind == 'found':
                    self.status.set(f'Found {data:,} candidates. Checking email syntax and domains…')
                elif kind == 'progress':
                    n, total = data
                    self.bar.configure(value=n / max(total, 1) * 100)
                    if not self.cancel.is_set():
                        self.status.set(f'Checked {n:,} of {total:,} unique domains…')
                elif kind == 'done':
                    self.set_busy(False)
                    if self.cancel.is_set():
                        self.status.set('Cancelled. No results saved.')
                        self.counts.set('No completed results')
                        continue
                    self.results = data
                    counts = Counter(r.status for r in data)
                    self.counts.set(f"Clean  {counts['clean']:,}     Rejected  {counts['rejected']:,}     Needs review  {counts['review']:,}     Duplicates  {counts['duplicate']:,}")
                    self.bar.configure(value=100)
                    self.status.set(f'Finished. {len(data):,} candidates processed. Double-click a result for details.' if data else 'No email candidates found. Use an Email column in Excel or visible email text in Word.')
                    self.save.configure(state='normal' if data else 'disabled')
                    self.show_results()
                elif kind in ('error', 'cancelled'):
                    self.set_busy(False)
                    self.counts.set('No completed results')
                    self.status.set('Cancelled. No results saved.' if kind == 'cancelled' else 'Unable to process this file.')
                    if kind == 'error':
                        messagebox.showerror('Validation failed', data)
        except queue.Empty:
            pass
        self.after(100, self.poll)

    def show_results(self):
        self.table.delete(*self.table.get_children())
        count = 0
        for i, result in enumerate(self.results):
            if self.filter.get() != 'All' and result.status != self.filter.get().lower():
                continue
            self.table.insert('', 'end', iid=str(i), values=(result.email, result.status.title(), result.reason, result.source))
            count += 1
            if count >= 2000:
                break

    def details(self, _):
        selected = self.table.selection()
        if selected:
            r = self.results[int(selected[0])]
            messagebox.showinfo('Email details', f'{r.email}\n\nStatus: {r.status}\n{r.reason}\n\nSource: {r.source}\nOriginal: {r.original}')

    def export(self):
        destination = filedialog.askdirectory(title='Choose where to save your results')
        if destination:
            try:
                folder = export_results(self.results, destination, self.source)
                self.status.set(f'Saved to {folder}')
                os.startfile(folder)
            except Exception as exc:
                messagebox.showerror('Export failed', str(exc))

    def close(self):
        self.cancel.set()
        self.destroy()


if __name__ == '__main__':
    EmailCleaner().mainloop()
