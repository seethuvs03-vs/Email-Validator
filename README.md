# Email Cleaner

For uploading the complete source to GitHub, see **GITHUB_UPLOAD.md**. Run `python package_github.py` to create a source ZIP without local credentials or contact data.

## Company-hosted web application

For the browser version, use **Setup_Server.bat** then **Start_Server.bat** on Windows Server. Staff access the server's URL and upload their files in a browser. Read **WINDOWS_SERVER_SETUP.md** for the complete installation, automatic startup and HTTPS instructions. The portable distribution is `dist/Email-Cleaner-Windows-Server.zip`.

The web app includes team sign-in, Excel/Word/CSV upload, progress, paginated results, clean CSV and Excel/ZIP downloads. It retains completed results for one hour. `sample_contacts.csv` is a fictional test file.

## Earlier desktop version

A local Windows app based on your original validator. Double-click **Validate_Emails.bat**, choose a file, click **Validate emails**, then **Save Excel + CSV results**.

Python 3.10 or newer is required. The launcher installs dependencies into a local `.venv` on first use; this initial step needs internet access. Domain validation also requires working DNS access.

## Files and results

- Excel `.xlsx` and `.xls`: scans all sheets. Columns headed Email, Emails, Email Address or Email Addresses retain malformed values too. Other cells contribute email-like tokens containing `@`. Multiple addresses can be separated by commas, semicolons or newlines.
- Word `.docx`: extracts visible addresses from paragraphs, tables, headers, footers and notes. Save legacy `.doc` files as `.docx` in Word first. Images, scanned documents and hyperlink-only targets are not read.
- CSV/TSV: scans all columns, supports common Excel encodings and delimiters.
- Text: one address per line; commas and semicolons are also supported.

Blank cells are ignored. Counts refer to extracted candidates, not spreadsheet rows. Formula cells require cached results saved by Excel. Password-protected files must be saved without encryption first.

Each export creates its own timestamped folder containing `validation_results.xlsx` and four CSV files:

- **Clean**: valid syntax, not on the disposable list, and a working mail-routing DNS record.
- **Rejected**: malformed address, known disposable domain, nonexistent domain, explicit null MX, or no mail-routing record.
- **Review**: temporary DNS failure or timeout; retry later.
- **Duplicate**: repeated normalized address. Local-part casing is preserved because it can be significant; domain casing and Unicode normalization are handled by email-validator.

Clean does **not** verify that a particular mailbox exists or guarantee delivery. No messages or SMTP probes are sent. The disposable seed list is deliberately small; use **Add disposable-domain list** to supply a maintained UTF-8 text file, one domain per line. Lines beginning with `#` are comments.

Files stay on the computer. DNS lookups disclose domain names to the configured DNS resolver. Exported CSV and Excel values are protected against spreadsheet formula execution.

## Changes from the supplied script

Added desktop upload, Excel/Word readers, source locations, cancellation, progress, result preview, and Excel/CSV export. DNS failures now remain uncertain instead of being treated as invalid. Explicit null MX is rejected; A/AAAA fallback is only attempted when MX records are absent. Domain lookups run concurrently and are reused within a validation run. Deduplication happens after normalization. Removed optional SMTP probing from the new app because network restrictions and server policies make its results unreliable.

## Command line and checks

```powershell
python -m pip install -r requirements.txt
python app.py
python email_validator_tool.py contacts.xlsx --outdir results
python -m unittest discover -s tests -v
```
