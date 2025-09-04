import json
data = json.load(open('file_cache_optimized.json'))
print('First 3 files:')
for i in range(3):
    print(f'{i+1}. {repr(data["files"][i])}')
    print(f'   Type: {type(data["files"][i])}')
