import os
import subprocess

def load_env_file(file_path='.env'):
    env_vars = {}
    with open(file_path, 'r') as file:
        for line in file:
            line = line.strip()
            if line and not line.startswith('#'):
                key, value = line.split('=', 1)
                env_vars[key.strip()] = value.strip()
    return env_vars

def update_heroku_config(app_name, env_vars):
    for key, value in env_vars.items():
        command = f'heroku config:set {key}="{value}" --app {app_name}'
        try:
            subprocess.run(command, shell=True, check=True)
            print(f"Successfully updated {key}")
        except subprocess.CalledProcessError as e:
            print(f"Failed to update {key}: {e}")

def main():
    app_name = 'epona'
    env_vars = load_env_file()
    
    if not env_vars:
        print("No environment variables found in .env file")
        return

    print(f"Updating Heroku Config Vars for app: {app_name}")
    update_heroku_config(app_name, env_vars)
    print("Config Var update process completed")

if __name__ == "__main__":
    main()