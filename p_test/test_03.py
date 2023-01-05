import pandas as pd
import numpy as np
import math

data1 = [[1,np.NaN],['A',4.1],[math.inf,'3']]
df1 = pd.DataFrame(data1)
df2 = pd.DataFrame(data=[[5,6],[7,8],[9,10]],index=[['A','B','B'],[3,4,5]]) #멀티인덱스 객체
print(df1)
print(df2)

path = "C:\\Users\\김경하\\Desktop\\이미지 변환\\"
df1.to_excel(excel_writer=path+'test.xlsx',storage_options=)