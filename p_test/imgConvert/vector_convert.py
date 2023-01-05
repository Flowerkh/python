import numpy as np
from PIL import Image

img = Image.open('C:\\Users\\김경하\\Desktop\\이미지 변환\\sign_202104.png').convert('RGBA')
arr = np.array(img)

# record the original shape
shape = arr.shape

# make a 1-dimensional view of arr
flat_arr = arr.ravel()

# convert it to a matrix
vector = np.matrix(flat_arr)

# do something to the vector
vector[:,::10] = 10000

# reform a numpy array of the original shape
arr2 = np.asarray(vector).reshape(shape)

# make a PIL image
img2 = Image.fromarray(arr2, 'RGBA')
img2.show()