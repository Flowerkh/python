import openpyxl as op
from openpyxl.workbook.protection import WorkbookProtection

wb = op.load_workbook("C:\\Users\\김경하\\Desktop\\이미지 변환\\invoice_xls.xlsx")
ws = wb.active
wb.security = WorkbookProtection(workBookPassword = '1234', lockStructure = True)

#wb.security.workbookPassword = '1234'
#wb.security.lockStructure = True

# Save Excel file
wb.save("C:\\Users\\김경하\\Desktop\\이미지 변환\\invoice_xls2.xlsx")