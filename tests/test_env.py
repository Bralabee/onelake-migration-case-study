import os

def load_env_file(env_file='.env'):
    # Check multiple possible locations for .env file
    possible_paths = [
        env_file,  # Current directory
        f"config/{env_file}",  # Config directory (after reorganization)
        f"../config/{env_file}",  # From tests/ to config/
        f"../../config/{env_file}"  # Alternative path
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            print(f'Loading {path}')
            with open(path, 'r') as f:
                for line in f:
                    if '=' in line and not line.strip().startswith('#'):
                        key, value = line.strip().split('=', 1)
                        os.environ[key] = value.strip('"\'')
                        print(f'Set {key} = {value[:20]}...')
            return
    
    print(f'No .env file found in any of these locations: {possible_paths}')

load_env_file()
print('TENANT_ID:', os.environ.get('TENANT_ID', 'NOT_FOUND')[:20])
