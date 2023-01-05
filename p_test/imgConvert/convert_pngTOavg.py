import aspose.words as aw
import os.path
from PIL import Image
'''
def change_file_size(original_path, change_path, qualty=1) :
    """
    Change Image Qualty
    :param original_path: 원본 경로
    :param change_path: 변경 후 새롭게 저장될 경로
    :param qualty: Qualty(품질) 퍼센트(기본 : 85%)
    :return:
    """
    if not os.path.exists(change_path):
        os.mkdir(change_path)
    try:
        ims_list = os.listdir(original_path)
        ims_list.sort()
    except FileNotFoundError as e:
        print("이미지 원본 디렉터리가 존재하지 않습니다...")
    success_cnt = 0
    fail_cnt = 0
    for filename in ims_list:
        file = original_path + filename
        try:
            im = Image.open(file)
            im.save(os.path.join(change_path, filename), qualty=qualty)
            print("+ 성공 : {success}\n - {success_path}".format(success=file, success_path=os.path.join(change_path, filename)))
            success_cnt += 1
        except Exception as e:
            print("+ 실패 : {fail}".format(fail=file))
            fail_cnt += 1
    print("\n성공 : {success_cnt} 건 / 실패 : {fail_cnt} 건".format(success_cnt=success_cnt, fail_cnt=fail_cnt))
'''
path = input()
file_list = os.listdir(path)

doc = aw.Document()
builder = aw.DocumentBuilder(doc)
saveOptions = aw.saving.ImageSaveOptions(aw.SaveFormat.SVG)

for img in file_list :
    name, ext = os.path.splitext(img)
    if(ext=='.png') :
        # find png filelist
        shape = builder.insert_image(path + img)

        # convert svg
        shape.get_shape_renderer().save(path + name + ".svg", saveOptions)
        #change_file_size('C:/Users/김경하/Desktop/이미지 변환/', 'C:/Users/김경하/Desktop/이미지 변환/')
