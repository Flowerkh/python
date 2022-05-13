import json

def get_config():
	try:
		with open('/home/discord/token.json') as json_file:
			json_data = json.load(json_file)
	except Exception as e:
		print('LOG: Error in reading config file, {}'.format(e))
		return None
	else:
		return json_data

path = "./discord/blacklist/black_list.txt"
black_list = []

with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()
        for line in lines:
                if line.strip("\n") != "안드레아Y":
                        black_list.append(line.strip('\n'))
with open(path, 'w', encoding="utf-8") as f:
	for val in black_list:
		f.write(f"{val}\n")


print(black_list)