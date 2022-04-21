import base64

sitename = 'cdffee1'
sitename_base64 = base64.b64encode(sitename.encode('ascii'))
sitename_base64_str = sitename_base64.decode('ascii')

print(sitename_base64)
print(sitename_base64_str)